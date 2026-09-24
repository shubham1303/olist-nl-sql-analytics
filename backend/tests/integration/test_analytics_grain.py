"""Every analytics view has exactly the grain its catalog entry declares."""

import pytest

from olist_nlsql.catalog import Relation, load_catalog
from tests.integration.helpers import Conn, row, scalar

RELATIONS = load_catalog().relations

# Expected rows per view, each derived from an independent raw-table count.
EXPECTED_ROWS = {
    "orders": "SELECT count(*) FROM raw.orders",
    "order_items": "SELECT count(*) FROM raw.order_items",
    "order_sellers": "SELECT count(*) FROM (SELECT DISTINCT order_id, seller_id FROM raw.order_items) s",
    "order_payments": "SELECT count(*) FROM raw.order_payments",
    "customers": "SELECT count(DISTINCT customer_unique_id) FROM raw.customers",
    "sellers": "SELECT count(*) FROM raw.sellers",
    "products": "SELECT count(*) FROM raw.products",
    # Categories are derived, so check against the known value (cross-checked with the
    # earlier SQL Server model, which produced the same 99,470 order-category rows).
    "order_categories": "SELECT 99470",
}


def test_every_relation_has_an_expected_row_count() -> None:
    assert {r.name for r in RELATIONS} == set(EXPECTED_ROWS)


@pytest.mark.parametrize("relation", RELATIONS, ids=lambda r: r.name)
def test_grain_key_is_unique_and_not_null(reader: Conn, relation: Relation) -> None:
    key = ", ".join(relation.grain_key)
    not_null = " AND ".join(f"{c} IS NOT NULL" for c in relation.grain_key)
    rows, distinct_keys, complete = row(
        reader,
        f"""SELECT count(*), count(DISTINCT ({key})), count(*) FILTER (WHERE {not_null})
            FROM analytics.{relation.name}""",
    )
    assert rows == distinct_keys == complete


@pytest.mark.parametrize("relation", RELATIONS, ids=lambda r: r.name)
def test_row_count_matches_source(owner: Conn, relation: Relation) -> None:
    expected = scalar(owner, EXPECTED_ROWS[relation.name])
    assert scalar(owner, f"SELECT count(*) FROM analytics.{relation.name}") == expected


def test_order_categories_sum_to_order_items(reader: Conn) -> None:
    assert scalar(reader, "SELECT sum(item_count) FROM order_categories") == 112_650
    assert scalar(reader, "SELECT sum(item_count) FROM order_sellers") == 112_650
    assert scalar(reader, "SELECT sum(item_count) FROM orders") == 112_650


def test_order_category_count_is_consistent(reader: Conn) -> None:
    mismatches = scalar(
        reader,
        """SELECT count(*) FROM order_categories oc
           WHERE oc.order_category_count <>
                 (SELECT count(*) FROM order_categories x WHERE x.order_id = oc.order_id)""",
    )
    assert mismatches == 0
