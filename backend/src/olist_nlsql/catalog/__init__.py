"""The analytics catalog (ADR 0005): the single source of truth for what the model
may see and what the SQL validator allows.

It defines relations (grain, grain key, columns, visibility), the relationships
between them, business metrics, the SQL function allowlist and the allowed cast
types. ``load_catalog()`` parses ``catalog.yaml`` strictly: unknown or missing keys,
unknown types and dangling references are errors, so a malformed catalog can never
silently widen or shrink what the validator allows.
"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml

ColumnType = Literal["text", "integer", "numeric", "boolean", "date", "timestamp"]
COLUMN_TYPES: frozenset[str] = frozenset(get_args(ColumnType))

Cardinality = Literal["one_to_many", "one_to_one"]
CARDINALITIES: frozenset[str] = frozenset(get_args(Cardinality))

FunctionKind = Literal["aggregate", "scalar", "window"]
FUNCTION_KINDS: frozenset[str] = frozenset(get_args(FunctionKind))


class CatalogError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: ColumnType
    description: str
    values: tuple[str, ...] | None = None  # exhaustive allowed values, when listed
    exposed: bool = True  # visible to the model and allowed by the validator
    # Order-level outcome repeated on every row of a bridge relation (ADR 0011).
    attributed: bool = False


@dataclass(frozen=True, slots=True)
class Relation:
    name: str
    description: str
    grain: str
    grain_key: tuple[str, ...]
    columns: tuple[Column, ...]
    exposed: bool
    caveats: tuple[str, ...] = ()
    # Bridge relations: the column(s) an attributed outcome must be grouped by.
    attribution_key: tuple[str, ...] = ()
    hidden_reason: str | None = None

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(name)

    @property
    def exposed_columns(self) -> tuple[Column, ...]:
        return tuple(c for c in self.columns if c.exposed)


@dataclass(frozen=True, slots=True)
class KeyPair:
    one: str  # column on the "one" side
    many: str  # column on the "many" side


@dataclass(frozen=True, slots=True)
class Relationship:
    name: str
    one: str  # relation that is unique on the keys
    many: str
    cardinality: Cardinality
    keys: tuple[KeyPair, ...]


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    name: str  # PostgreSQL name, upper case
    kind: FunctionKind
    description: str
    # Aggregates only: True when duplicated input rows change the result
    # (SUM, AVG, COUNT), False when they cannot (MIN, MAX).
    duplicate_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class MetricVariant:
    relation: str
    expression: str


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    label: str
    definition: str
    relation: str
    unit: str
    exclusions: tuple[str, ...]
    caveats: tuple[str, ...]
    aliases: tuple[str, ...]
    # Exactly one of: an aggregate expression over `relation`, or a full query.
    expression: str | None = None
    query: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    rationale: str | None = None
    variants: tuple[MetricVariant, ...] = ()

    def sql(self) -> str:
        """A complete SELECT computing this metric."""
        if self.query is not None:
            return self.query
        # Built only from trusted catalog content, never from user input.
        return f"SELECT {self.expression} AS {self.name} FROM analytics.{self.relation}"  # noqa: S608


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    term: str
    meaning: str


@dataclass(frozen=True, slots=True)
class Catalog:
    version: int
    schema: str
    dataset_notes: tuple[str, ...]
    glossary: tuple[GlossaryTerm, ...]
    relations: tuple[Relation, ...]
    relationships: tuple[Relationship, ...]
    metrics: tuple[Metric, ...]
    functions: tuple[FunctionSpec, ...]
    cast_types: tuple[str, ...]

    def relation(self, name: str) -> Relation:
        for relation in self.relations:
            if relation.name == name:
                return relation
        raise KeyError(name)

    @property
    def exposed_relations(self) -> tuple[Relation, ...]:
        return tuple(r for r in self.relations if r.exposed)

    def metrics_for(self, relation: str) -> tuple[Metric, ...]:
        """Metrics computed on ``relation`` directly or through a variant."""
        return tuple(
            m
            for m in self.metrics
            if m.relation == relation or any(v.relation == relation for v in m.variants)
        )

    def relationships_for(self, relation: str) -> tuple[Relationship, ...]:
        return tuple(r for r in self.relationships if relation in (r.one, r.many))


def _mapping(value: object, where: str, required: set[str], optional: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError(f"{where}: expected a mapping, got {type(value).__name__}")
    keys = set(value)
    if missing := required - keys:
        raise CatalogError(f"{where}: missing keys {sorted(missing)}")
    if unknown := keys - required - optional:
        raise CatalogError(f"{where}: unknown keys {sorted(map(str, unknown))}")
    return cast(dict[str, Any], value)


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{where}: expected non-empty text, got {value!r}")
    return value.strip()


def _texts(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CatalogError(f"{where}: expected a list")
    return tuple(_text(item, f"{where}[{i}]") for i, item in enumerate(value))


def _bool(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise CatalogError(f"{where}: expected true or false, got {value!r}")
    return value


def _column(raw: object, where: str) -> Column:
    data = _mapping(
        raw, where, {"name", "type", "description"}, {"values", "exposed", "attributed"}
    )
    column_type = _text(data["type"], f"{where}.type")
    if column_type not in COLUMN_TYPES:
        raise CatalogError(f"{where}: unknown type {column_type!r}")
    return Column(
        name=_text(data["name"], f"{where}.name"),
        type=cast(ColumnType, column_type),
        description=_text(data["description"], f"{where}.description"),
        values=_texts(data["values"], f"{where}.values") if "values" in data else None,
        exposed=_bool(data.get("exposed", True), f"{where}.exposed"),
        attributed=_bool(data.get("attributed", False), f"{where}.attributed"),
    )


def _relation(raw: object, where: str) -> Relation:
    data = _mapping(
        raw,
        where,
        {"name", "description", "grain", "grain_key", "exposed", "columns"},
        {"caveats", "attribution_key", "hidden_reason"},
    )
    name = _text(data["name"], f"{where}.name")
    columns = tuple(
        _column(c, f"{where}({name}).columns[{i}]") for i, c in enumerate(data["columns"])
    )
    names = [c.name for c in columns]
    if len(names) != len(set(names)):
        raise CatalogError(f"relation {name}: duplicate column names")
    exposed_names = {c.name for c in columns if c.exposed}
    grain_key = _texts(data["grain_key"], f"{where}.grain_key")
    if unknown := set(grain_key) - exposed_names:
        raise CatalogError(f"relation {name}: grain key columns not exposed: {sorted(unknown)}")
    attribution_key = _texts(data.get("attribution_key", []), f"{where}.attribution_key")
    if unknown := set(attribution_key) - exposed_names:
        raise CatalogError(f"relation {name}: attribution key not exposed: {sorted(unknown)}")
    if any(c.attributed for c in columns) and not attribution_key:
        raise CatalogError(f"relation {name}: attributed columns need an attribution_key")
    exposed = _bool(data["exposed"], f"{where}.exposed")
    hidden_reason = data.get("hidden_reason")
    if not exposed and hidden_reason is None:
        raise CatalogError(f"relation {name}: hidden relations need a hidden_reason")
    return Relation(
        name=name,
        description=_text(data["description"], f"{where}.description"),
        grain=_text(data["grain"], f"{where}.grain"),
        grain_key=grain_key,
        columns=columns,
        exposed=exposed,
        caveats=_texts(data.get("caveats", []), f"{where}.caveats"),
        attribution_key=attribution_key,
        hidden_reason=_text(hidden_reason, f"{where}.hidden_reason") if hidden_reason else None,
    )


def _relationship(raw: object, where: str, relations: dict[str, Relation]) -> Relationship:
    data = _mapping(raw, where, {"name", "one", "many", "cardinality", "keys"}, set())
    name = _text(data["name"], f"{where}.name")
    cardinality = _text(data["cardinality"], f"{where}.cardinality")
    if cardinality not in CARDINALITIES:
        raise CatalogError(f"relationship {name}: unknown cardinality {cardinality!r}")
    one_name, many_name = _text(data["one"], f"{where}.one"), _text(data["many"], f"{where}.many")
    for side in (one_name, many_name):
        if side not in relations or not relations[side].exposed:
            raise CatalogError(f"relationship {name}: {side!r} is not an exposed relation")
    keys = tuple(
        KeyPair(one=_text(k["one"], f"{where}.keys.one"), many=_text(k["many"], f"{where}.keys"))
        for k in (_mapping(k, f"{where}.keys", {"one", "many"}, set()) for k in data["keys"])
    )
    if not keys:
        raise CatalogError(f"relationship {name}: needs at least one key pair")
    one, many = relations[one_name], relations[many_name]
    # The "one" side must be unique on the keys: they must be exactly its grain key.
    if {k.one for k in keys} != set(one.grain_key):
        raise CatalogError(f"relationship {name}: keys must be the grain key of {one_name}")
    if cardinality == "one_to_one" and {k.many for k in keys} != set(many.grain_key):
        raise CatalogError(f"relationship {name}: one_to_one keys must be both grain keys")
    for pair in keys:
        for relation, column in ((one, pair.one), (many, pair.many)):
            if column not in {c.name for c in relation.exposed_columns}:
                raise CatalogError(f"relationship {name}: {relation.name}.{column} not exposed")
    return Relationship(
        name=name,
        one=one_name,
        many=many_name,
        cardinality=cast(Cardinality, cardinality),
        keys=keys,
    )


def _function(raw: object, where: str) -> FunctionSpec:
    data = _mapping(raw, where, {"name", "kind", "description"}, {"duplicate_sensitive"})
    name = _text(data["name"], f"{where}.name")
    if name != name.upper():
        raise CatalogError(f"{where}: function names must be upper case ({name})")
    kind = _text(data["kind"], f"{where}.kind")
    if kind not in FUNCTION_KINDS:
        raise CatalogError(f"{where}: unknown function kind {kind!r}")
    if kind == "aggregate" and "duplicate_sensitive" not in data:
        raise CatalogError(f"{where}: aggregate {name} must declare duplicate_sensitive")
    if kind != "aggregate" and "duplicate_sensitive" in data:
        raise CatalogError(f"{where}: duplicate_sensitive applies to aggregates only")
    return FunctionSpec(
        name=name,
        kind=cast(FunctionKind, kind),
        description=_text(data["description"], f"{where}.description"),
        duplicate_sensitive=_bool(data.get("duplicate_sensitive", False), f"{where}"),
    )


def _metric(raw: object, where: str, relations: dict[str, Relation]) -> Metric:
    data = _mapping(
        raw,
        where,
        {"name", "label", "definition", "relation", "unit", "exclusions", "caveats", "aliases"},
        {"expression", "query", "numerator", "denominator", "rationale", "variants"},
    )
    name = _text(data["name"], f"{where}.name")
    if ("expression" in data) == ("query" in data):
        raise CatalogError(f"metric {name}: define exactly one of expression or query")
    variants = tuple(
        MetricVariant(
            relation=_text(v["relation"], f"{where}({name}).variants.relation"),
            expression=_text(v["expression"], f"{where}({name}).variants.expression"),
        )
        for v in (
            _mapping(v, f"{where}({name}).variants[{i}]", {"relation", "expression"}, set())
            for i, v in enumerate(data.get("variants", []))
        )
    )

    def optional(key: str) -> str | None:
        return _text(data[key], f"{where}.{key}") if key in data else None

    metric = Metric(
        name=name,
        label=_text(data["label"], f"{where}.label"),
        definition=_text(data["definition"], f"{where}.definition"),
        relation=_text(data["relation"], f"{where}.relation"),
        unit=_text(data["unit"], f"{where}.unit"),
        exclusions=_texts(data["exclusions"], f"{where}.exclusions"),
        caveats=_texts(data["caveats"], f"{where}.caveats"),
        aliases=_texts(data["aliases"], f"{where}.aliases"),
        expression=optional("expression"),
        query=optional("query"),
        numerator=optional("numerator"),
        denominator=optional("denominator"),
        rationale=optional("rationale"),
        variants=variants,
    )
    # The model sees metrics, so they may only reference exposed relations.
    for relation in [metric.relation, *(v.relation for v in metric.variants)]:
        if relation not in relations or not relations[relation].exposed:
            raise CatalogError(f"metric {name}: {relation!r} is not an exposed relation")
    return metric


def _unique(names: list[str], what: str) -> None:
    if len(names) != len(set(names)):
        raise CatalogError(f"duplicate {what} names")


def parse_catalog(document: object) -> Catalog:
    data = _mapping(
        document,
        "catalog",
        {"version", "dataset", "relations", "relationships", "metrics", "functions", "cast_types"},
        {"glossary"},
    )
    if not isinstance(data["version"], int):
        raise CatalogError("version must be an integer")
    dataset = _mapping(data["dataset"], "dataset", {"name", "currency", "schema", "notes"}, set())
    glossary = tuple(
        GlossaryTerm(
            term=_text(g["term"], "glossary.term"), meaning=_text(g["meaning"], "glossary")
        )
        for g in (
            _mapping(g, f"glossary[{i}]", {"term", "meaning"}, set())
            for i, g in enumerate(data.get("glossary", []))
        )
    )
    relations = tuple(_relation(r, f"relations[{i}]") for i, r in enumerate(data["relations"]))
    _unique([r.name for r in relations], "relation")
    by_name = {r.name: r for r in relations}
    relationships = tuple(
        _relationship(r, f"relationships[{i}]", by_name)
        for i, r in enumerate(data["relationships"])
    )
    _unique([r.name for r in relationships], "relationship")
    metrics = tuple(_metric(m, f"metrics[{i}]", by_name) for i, m in enumerate(data["metrics"]))
    _unique([m.name for m in metrics], "metric")
    functions = tuple(_function(f, f"functions[{i}]") for i, f in enumerate(data["functions"]))
    _unique([f.name for f in functions], "function")
    return Catalog(
        version=data["version"],
        schema=_text(dataset["schema"], "dataset.schema"),
        dataset_notes=_texts(dataset["notes"], "dataset.notes"),
        glossary=glossary,
        relations=relations,
        relationships=relationships,
        metrics=metrics,
        functions=functions,
        cast_types=_texts(data["cast_types"], "cast_types"),
    )


def load_catalog(path: Path | None = None) -> Catalog:
    """Load and validate the catalog (defaults to the packaged ``catalog.yaml``)."""
    if path is None:
        text = resources.files("olist_nlsql.catalog").joinpath("catalog.yaml").read_text("utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    return parse_catalog(yaml.safe_load(text))
