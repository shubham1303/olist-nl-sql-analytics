"""The analytics catalog (ADR 0005): relations, columns and metric definitions.

``load_catalog()`` parses ``catalog.yaml`` strictly: unknown or missing keys,
unknown column types and dangling references are errors, so a malformed catalog
can never silently shrink the schema the model sees or the validator allows.
"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml

ColumnType = Literal["text", "integer", "numeric", "boolean", "date", "timestamp"]
COLUMN_TYPES: frozenset[str] = frozenset(get_args(ColumnType))


class CatalogError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: ColumnType
    description: str
    values: tuple[str, ...] | None = None  # exhaustive allowed values, when listed


@dataclass(frozen=True, slots=True)
class Relation:
    name: str
    description: str
    grain: str
    primary_key: tuple[str, ...]
    columns: tuple[Column, ...]
    caveats: tuple[str, ...] = ()

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(name)


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
    expression: str
    unit: str
    exclusions: tuple[str, ...]
    caveats: tuple[str, ...]
    aliases: tuple[str, ...]
    numerator: str | None = None
    denominator: str | None = None
    rationale: str | None = None
    variants: tuple[MetricVariant, ...] = ()


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
    metrics: tuple[Metric, ...]

    def relation(self, name: str) -> Relation:
        for relation in self.relations:
            if relation.name == name:
                return relation
        raise KeyError(name)


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


def _column(raw: object, where: str) -> Column:
    data = _mapping(raw, where, {"name", "type", "description"}, {"values"})
    column_type = _text(data["type"], f"{where}.type")
    if column_type not in COLUMN_TYPES:
        raise CatalogError(f"{where}: unknown type {column_type!r}")
    values = _texts(data["values"], f"{where}.values") if "values" in data else None
    return Column(
        name=_text(data["name"], f"{where}.name"),
        type=cast(ColumnType, column_type),
        description=_text(data["description"], f"{where}.description"),
        values=values,
    )


def _relation(raw: object, where: str) -> Relation:
    data = _mapping(
        raw, where, {"name", "description", "grain", "primary_key", "columns"}, {"caveats"}
    )
    name = _text(data["name"], f"{where}.name")
    columns = tuple(
        _column(c, f"{where}({name}).columns[{i}]") for i, c in enumerate(data["columns"])
    )
    names = [c.name for c in columns]
    if len(names) != len(set(names)):
        raise CatalogError(f"relation {name}: duplicate column names")
    primary_key = _texts(data["primary_key"], f"{where}.primary_key")
    if unknown := set(primary_key) - set(names):
        raise CatalogError(f"relation {name}: primary key columns not defined: {sorted(unknown)}")
    return Relation(
        name=name,
        description=_text(data["description"], f"{where}.description"),
        grain=_text(data["grain"], f"{where}.grain"),
        primary_key=primary_key,
        columns=columns,
        caveats=_texts(data.get("caveats", []), f"{where}.caveats"),
    )


def _metric(raw: object, where: str, relations: set[str]) -> Metric:
    data = _mapping(
        raw,
        where,
        {
            "name",
            "label",
            "definition",
            "relation",
            "expression",
            "unit",
            "exclusions",
            "caveats",
            "aliases",
        },
        {"numerator", "denominator", "rationale", "variants"},
    )
    name = _text(data["name"], f"{where}.name")
    variants = tuple(
        MetricVariant(
            relation=_text(v["relation"], f"{where}({name}).variants[{i}].relation"),
            expression=_text(v["expression"], f"{where}({name}).variants[{i}].expression"),
        )
        for i, v in enumerate(
            _mapping(v, f"{where}({name}).variants[{i}]", {"relation", "expression"}, set())
            for i, v in enumerate(data.get("variants", []))
        )
    )
    metric = Metric(
        name=name,
        label=_text(data["label"], f"{where}.label"),
        definition=_text(data["definition"], f"{where}.definition"),
        relation=_text(data["relation"], f"{where}.relation"),
        expression=_text(data["expression"], f"{where}.expression"),
        unit=_text(data["unit"], f"{where}.unit"),
        exclusions=_texts(data["exclusions"], f"{where}.exclusions"),
        caveats=_texts(data["caveats"], f"{where}.caveats"),
        aliases=_texts(data["aliases"], f"{where}.aliases"),
        numerator=_text(data["numerator"], f"{where}.numerator") if "numerator" in data else None,
        denominator=(
            _text(data["denominator"], f"{where}.denominator") if "denominator" in data else None
        ),
        rationale=_text(data["rationale"], f"{where}.rationale") if "rationale" in data else None,
        variants=variants,
    )
    for relation in [metric.relation, *(v.relation for v in metric.variants)]:
        if relation not in relations:
            raise CatalogError(f"metric {name}: unknown relation {relation!r}")
    return metric


def parse_catalog(document: object) -> Catalog:
    data = _mapping(
        document, "catalog", {"version", "dataset", "relations", "metrics"}, {"glossary"}
    )
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
    relation_names = [r.name for r in relations]
    if len(relation_names) != len(set(relation_names)):
        raise CatalogError("duplicate relation names")
    metrics = tuple(
        _metric(m, f"metrics[{i}]", set(relation_names)) for i, m in enumerate(data["metrics"])
    )
    metric_names = [m.name for m in metrics]
    if len(metric_names) != len(set(metric_names)):
        raise CatalogError("duplicate metric names")
    if not isinstance(data["version"], int):
        raise CatalogError("version must be an integer")
    return Catalog(
        version=data["version"],
        schema=_text(dataset["schema"], "dataset.schema"),
        dataset_notes=_texts(dataset["notes"], "dataset.notes"),
        glossary=glossary,
        relations=relations,
        metrics=metrics,
    )


def load_catalog(path: Path | None = None) -> Catalog:
    """Load and validate the catalog (defaults to the packaged ``catalog.yaml``)."""
    if path is None:
        text = resources.files("olist_nlsql.catalog").joinpath("catalog.yaml").read_text("utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    return parse_catalog(yaml.safe_load(text))
