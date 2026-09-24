"""The validator's view of the catalog. Everything here is derived from catalog.yaml
and Settings; nothing is configured separately (ADR 0005, ADR 0014)."""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlglot import exp

from olist_nlsql.catalog import Catalog, FunctionSpec, Relationship
from olist_nlsql.config import Settings

ColumnRef = tuple[str, str]  # (relation, column)


@dataclass(frozen=True, slots=True)
class RelationPolicy:
    name: str
    columns: Mapping[str, str]  # exposed column -> logical type
    hidden_columns: frozenset[str]
    grain_key: frozenset[str]
    attribution_key: frozenset[str]
    attributed: frozenset[str]

    @property
    def is_bridge(self) -> bool:
        return bool(self.attribution_key)


@dataclass(frozen=True, slots=True)
class Limits:
    max_rows: int
    max_sql_chars: int
    max_joins: int


# Logical catalog types -> sqlglot schema types (used only for column resolution).
_SCHEMA_TYPES = {
    "text": "text",
    "integer": "int",
    "numeric": "numeric",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "timestamp",
}


def _key_domains(relationships: tuple[Relationship, ...]) -> dict[ColumnRef, ColumnRef]:
    """Union-find over relationship key pairs: columns in one domain may be joined."""
    parent: dict[ColumnRef, ColumnRef] = {}

    def find(node: ColumnRef) -> ColumnRef:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for relationship in relationships:
        for pair in relationship.keys:
            a, b = find((relationship.one, pair.one)), find((relationship.many, pair.many))
            if a != b:
                parent[b] = a
    return {node: find(node) for node in list(parent)}


@dataclass(frozen=True, slots=True)
class Policy:
    schema: str
    relations: Mapping[str, RelationPolicy]
    hidden_relations: Mapping[str, str]  # name -> reason / alternative
    relationships: tuple[Relationship, ...]
    key_domains: Mapping[ColumnRef, ColumnRef]
    functions: Mapping[str, FunctionSpec]
    cast_types: frozenset[exp.DType]
    limits: Limits

    @classmethod
    def from_catalog(cls, catalog: Catalog, settings: Settings) -> "Policy":
        relations = {
            r.name: RelationPolicy(
                name=r.name,
                columns={c.name: c.type for c in r.exposed_columns},
                hidden_columns=frozenset(c.name for c in r.columns if not c.exposed),
                grain_key=frozenset(r.grain_key),
                attribution_key=frozenset(r.attribution_key),
                attributed=frozenset(c.name for c in r.columns if c.attributed),
            )
            for r in catalog.exposed_relations
        }
        return cls(
            schema=catalog.schema,
            relations=relations,
            hidden_relations={
                r.name: r.hidden_reason or "" for r in catalog.relations if not r.exposed
            },
            relationships=catalog.relationships,
            key_domains=_key_domains(catalog.relationships),
            functions={f.name: f for f in catalog.functions},
            cast_types=frozenset(
                exp.DataType.build(t, dialect="postgres").this for t in catalog.cast_types
            ),
            limits=Limits(
                max_rows=settings.max_result_rows,
                max_sql_chars=settings.max_sql_chars,
                max_joins=settings.max_joins,
            ),
        )

    def sqlglot_schema(self) -> dict[str, object]:
        return {
            self.schema: {
                name: {col: _SCHEMA_TYPES[t] for col, t in rel.columns.items()}
                for name, rel in self.relations.items()
            }
        }

    def same_domain(self, left: ColumnRef, right: ColumnRef) -> bool:
        """True when two catalog columns may be joined: identical, or related keys."""
        if left == right:
            return True
        a, b = self.key_domains.get(left), self.key_domains.get(right)
        return a is not None and a == b

    def relationships_between(self, a: str, b: str) -> tuple[Relationship, ...]:
        return tuple(r for r in self.relationships if {r.one, r.many} == {a, b})
