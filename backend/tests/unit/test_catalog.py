import copy
from importlib import resources
from typing import Any

import pytest
import yaml

from olist_nlsql.catalog import COLUMN_TYPES, CatalogError, load_catalog, parse_catalog

ALL_RELATIONS = {
    "orders",
    "order_items",
    "order_sellers",
    "order_categories",
    "order_payments",
    "customers",
    "sellers",
    "products",
}
EXPOSED_RELATIONS = ALL_RELATIONS - {"customers", "sellers"}

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


@pytest.fixture
def document() -> dict[str, Any]:
    text = resources.files("olist_nlsql.catalog").joinpath("catalog.yaml").read_text("utf-8")
    loaded: dict[str, Any] = yaml.safe_load(text)
    return loaded


def relation_doc(doc: dict[str, Any], name: str) -> dict[str, Any]:
    return next(r for r in doc["relations"] if r["name"] == name)


# ---------------------------------------------------------------- packaged catalog


def test_packaged_catalog_loads() -> None:
    catalog = load_catalog()
    assert catalog.schema == "analytics"
    assert {r.name for r in catalog.relations} == ALL_RELATIONS
    assert {r.name for r in catalog.exposed_relations} == EXPOSED_RELATIONS


def test_lifetime_summaries_are_hidden_with_a_reason() -> None:
    catalog = load_catalog()
    for name in ("customers", "sellers"):
        relation = catalog.relation(name)
        assert not relation.exposed
        assert relation.hidden_reason and "date filter" in relation.hidden_reason
    hidden = {c.name for c in catalog.relation("products").columns if not c.exposed}
    assert hidden == {"units_sold", "order_count", "total_revenue"}


def test_every_exposed_relation_documents_grain_and_keys() -> None:
    for relation in load_catalog().exposed_relations:
        assert relation.grain and relation.grain_key and relation.description
        assert all(c.type in COLUMN_TYPES for c in relation.columns)


def test_relationships_connect_every_fact_view_to_orders() -> None:
    catalog = load_catalog()
    pairs = {(r.one, r.many) for r in catalog.relationships}
    for many in ("order_items", "order_sellers", "order_categories", "order_payments"):
        assert ("orders", many) in pairs
    assert ("products", "order_items") in pairs
    assert all(r.cardinality == "one_to_many" for r in catalog.relationships)


def test_bridge_relations_mark_attributed_outcomes() -> None:
    catalog = load_catalog()
    for name, key in (
        ("order_sellers", ("seller_id",)),
        ("order_categories", ("product_category",)),
    ):
        relation = catalog.relation(name)
        assert relation.attribution_key == key
        attributed = {c.name for c in relation.columns if c.attributed}
        assert attributed == {
            "delivery_status", "is_late", "delivery_days",
            "delivery_delay_days", "has_review", "review_score",
        }  # fmt: skip
        assert "revenue" not in attributed


def test_required_metrics_are_defined() -> None:
    names = {m.name for m in load_catalog().metrics}
    assert names >= REQUIRED_METRICS


def test_every_metric_is_fully_documented() -> None:
    for metric in load_catalog().metrics:
        assert metric.aliases, metric.name
        assert metric.definition, metric.name
        if metric.unit == "ratio":
            assert metric.numerator and metric.denominator, metric.name


def test_relevant_metrics_are_derived_per_relation() -> None:
    catalog = load_catalog()
    assert {m.name for m in catalog.metrics_for("order_payments")} == {"payment_value"}
    assert "revenue" in {m.name for m in catalog.metrics_for("order_categories")}


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
    assert revenue.label == "Merchandise revenue"
    assert "Freight (see freight_value)." in revenue.exclusions


def test_function_allowlist_excludes_dangerous_and_relative_time_functions() -> None:
    names = {f.name for f in load_catalog().functions}
    assert {"COUNT", "SUM", "AVG", "DATE_TRUNC", "EXTRACT", "COALESCE"} <= names
    forbidden = {"PG_SLEEP", "NOW", "CURRENT_DATE", "SET_CONFIG", "CURRENT_SETTING", "PG_READ_FILE"}
    assert not names & forbidden


def test_min_and_max_are_the_only_duplicate_safe_numeric_aggregates() -> None:
    aggregates = {
        f.name: f.duplicate_sensitive for f in load_catalog().functions if f.kind == "aggregate"
    }
    assert {n for n, sensitive in aggregates.items() if not sensitive} == {
        "MIN", "MAX", "BOOL_OR", "BOOL_AND",
    }  # fmt: skip


# ---------------------------------------------------------------- strict parsing


def test_unknown_key_is_rejected(document: dict[str, Any]) -> None:
    document["relations"][0]["columns"][0]["colour"] = "red"
    with pytest.raises(CatalogError, match="unknown keys"):
        parse_catalog(document)


def test_flow_mapping_comma_mistake_is_rejected(document: dict[str, Any]) -> None:
    # An unquoted comma in a YAML flow mapping silently creates extra keys.
    document["relations"][0]["columns"][0] = yaml.safe_load(
        "{name: order_id, type: text, description: one, two}"
    )
    with pytest.raises(CatalogError, match="unknown keys"):
        parse_catalog(document)


def test_unknown_column_type_is_rejected(document: dict[str, Any]) -> None:
    document["relations"][0]["columns"][0]["type"] = "varchar"
    with pytest.raises(CatalogError, match="unknown type"):
        parse_catalog(document)


def test_grain_key_must_reference_exposed_columns(document: dict[str, Any]) -> None:
    document["relations"][0]["grain_key"] = ["nope"]
    with pytest.raises(CatalogError, match="grain key"):
        parse_catalog(document)


def test_duplicate_column_is_rejected(document: dict[str, Any]) -> None:
    columns = document["relations"][0]["columns"]
    columns.append(copy.deepcopy(columns[0]))
    with pytest.raises(CatalogError, match="duplicate column"):
        parse_catalog(document)


def test_hidden_relation_needs_a_reason(document: dict[str, Any]) -> None:
    del relation_doc(document, "customers")["hidden_reason"]
    with pytest.raises(CatalogError, match="hidden_reason"):
        parse_catalog(document)


def test_attributed_columns_need_an_attribution_key(document: dict[str, Any]) -> None:
    del relation_doc(document, "order_sellers")["attribution_key"]
    with pytest.raises(CatalogError, match="attribution_key"):
        parse_catalog(document)


def test_metric_on_hidden_relation_is_rejected(document: dict[str, Any]) -> None:
    document["metrics"][0]["relation"] = "customers"
    with pytest.raises(CatalogError, match="not an exposed relation"):
        parse_catalog(document)


def test_metric_needs_exactly_one_of_expression_or_query(document: dict[str, Any]) -> None:
    document["metrics"][0]["query"] = "SELECT 1"
    with pytest.raises(CatalogError, match="exactly one"):
        parse_catalog(document)


def test_relationship_one_side_must_be_unique(document: dict[str, Any]) -> None:
    # order_items is not unique on order_id, so it cannot be the "one" side.
    document["relationships"][0].update(one="order_items", many="orders")
    with pytest.raises(CatalogError, match="grain key of order_items"):
        parse_catalog(document)


def test_relationship_to_hidden_relation_is_rejected(document: dict[str, Any]) -> None:
    document["relationships"][0]["many"] = "customers"
    with pytest.raises(CatalogError, match="not an exposed relation"):
        parse_catalog(document)


def test_relationship_key_must_exist(document: dict[str, Any]) -> None:
    document["relationships"][0]["keys"] = [{"one": "order_id", "many": "no_such_column"}]
    with pytest.raises(CatalogError, match="not exposed"):
        parse_catalog(document)


def test_aggregate_must_declare_duplicate_sensitivity(document: dict[str, Any]) -> None:
    count = next(f for f in document["functions"] if f["name"] == "COUNT")
    del count["duplicate_sensitive"]
    with pytest.raises(CatalogError, match="duplicate_sensitive"):
        parse_catalog(document)


def test_function_names_must_be_upper_case(document: dict[str, Any]) -> None:
    document["functions"][0]["name"] = "count"
    with pytest.raises(CatalogError, match="upper case"):
        parse_catalog(document)
