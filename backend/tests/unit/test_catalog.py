import copy
from typing import Any

import pytest
import yaml

from olist_nlsql.catalog import COLUMN_TYPES, CatalogError, load_catalog, parse_catalog

EXPECTED_RELATIONS = {
    "orders",
    "order_items",
    "order_sellers",
    "order_categories",
    "order_payments",
    "customers",
    "sellers",
    "products",
}

REQUIRED_METRICS = {
    "order_count",
    "delivered_order_count",
    "canceled_order_count",
    "revenue",
    "average_order_value",
    "items_sold",
    "average_review_score",
    "late_delivery_rate",
    "average_delivery_days",
    "repeat_customer_rate",
}


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    from importlib import resources

    text = resources.files("olist_nlsql.catalog").joinpath("catalog.yaml").read_text("utf-8")
    loaded: dict[str, Any] = yaml.safe_load(text)
    return loaded


def test_packaged_catalog_loads() -> None:
    catalog = load_catalog()
    assert catalog.schema == "analytics"
    assert {r.name for r in catalog.relations} == EXPECTED_RELATIONS


def test_required_metrics_are_defined() -> None:
    names = {m.name for m in load_catalog().metrics}
    assert names >= REQUIRED_METRICS


def test_every_metric_is_fully_documented() -> None:
    for metric in load_catalog().metrics:
        assert metric.aliases, metric.name
        assert metric.definition, metric.name
        if metric.unit == "ratio":
            assert metric.numerator and metric.denominator, metric.name


def test_geolocation_is_not_exposed() -> None:
    catalog = load_catalog()
    names = {r.name for r in catalog.relations}
    columns = {c.name for r in catalog.relations for c in r.columns}
    assert not any("geolocation" in n for n in names)
    assert not any(c.endswith(("_lat", "_lng", "_zip_code_prefix")) for c in columns)


def test_raw_customer_id_is_not_exposed() -> None:
    columns = {c.name for r in load_catalog().relations for c in r.columns}
    assert "customer_id" not in columns
    assert "customer_unique_id" in columns


def test_revenue_has_a_documented_rationale() -> None:
    revenue = next(m for m in load_catalog().metrics if m.name == "revenue")
    assert revenue.rationale
    assert "Freight (see freight_value)." in revenue.exclusions


def test_unknown_key_is_rejected(document: dict[str, Any]) -> None:
    doc = copy.deepcopy(document)
    doc["relations"][0]["columns"][0]["colour"] = "red"
    with pytest.raises(CatalogError, match="unknown keys"):
        parse_catalog(doc)


def test_flow_mapping_comma_mistake_is_rejected() -> None:
    # An unquoted comma in a YAML flow mapping silently creates extra keys.
    broken = yaml.safe_load("{name: x, type: text, description: one, two}")
    doc = {
        "version": 1,
        "dataset": {"name": "d", "currency": "BRL", "schema": "analytics", "notes": []},
        "relations": [
            {
                "name": "r",
                "description": "d",
                "grain": "g",
                "primary_key": ["x"],
                "columns": [broken],
            }
        ],
        "metrics": [],
    }
    with pytest.raises(CatalogError, match="unknown keys"):
        parse_catalog(doc)


def test_unknown_column_type_is_rejected(document: dict[str, Any]) -> None:
    doc = copy.deepcopy(document)
    doc["relations"][0]["columns"][0]["type"] = "varchar"
    assert "varchar" not in COLUMN_TYPES
    with pytest.raises(CatalogError, match="unknown type"):
        parse_catalog(doc)


def test_metric_with_unknown_relation_is_rejected(document: dict[str, Any]) -> None:
    doc = copy.deepcopy(document)
    doc["metrics"][0]["relation"] = "raw_orders"
    with pytest.raises(CatalogError, match="unknown relation"):
        parse_catalog(doc)


def test_primary_key_must_reference_columns(document: dict[str, Any]) -> None:
    doc = copy.deepcopy(document)
    doc["relations"][0]["primary_key"] = ["nope"]
    with pytest.raises(CatalogError, match="primary key"):
        parse_catalog(doc)


def test_duplicate_column_is_rejected(document: dict[str, Any]) -> None:
    doc = copy.deepcopy(document)
    columns = doc["relations"][0]["columns"]
    columns.append(copy.deepcopy(columns[0]))
    with pytest.raises(CatalogError, match="duplicate column"):
        parse_catalog(doc)
