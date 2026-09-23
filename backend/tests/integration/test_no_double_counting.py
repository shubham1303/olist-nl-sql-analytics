"""Money and counts must add up identically at every grain and match the raw data.

A fan-out join anywhere in the analytics layer would make one of these totals
larger than the raw source.
"""

from decimal import Decimal

from tests.integration.helpers import Conn, scalar

REVENUE = Decimal("13494400.74")

# Raw computation of canonical revenue, independent of every view.
RAW_REVENUE_SQL = """
    SELECT sum(i.price) FROM raw.order_items i
    JOIN raw.orders o USING (order_id)
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
"""


def test_raw_revenue(owner: Conn) -> None:
    assert scalar(owner, RAW_REVENUE_SQL) == REVENUE


def test_revenue_is_identical_across_all_views(reader: Conn) -> None:
    totals = {
        view: scalar(reader, f"SELECT sum({column}) FROM {view}")
        for view, column in [
            ("orders", "revenue"),
            ("order_items", "revenue"),
            ("order_sellers", "revenue"),
            ("order_categories", "revenue"),
            ("customers", "total_revenue"),
            ("sellers", "total_revenue"),
            ("products", "total_revenue"),
        ]
    }
    assert set(totals.values()) == {REVENUE}, totals


def test_gross_item_value_matches_raw(owner: Conn, reader: Conn) -> None:
    raw_total = scalar(owner, "SELECT sum(price) FROM raw.order_items")
    for view in ["orders", "order_sellers", "order_categories"]:
        assert scalar(reader, f"SELECT sum(item_price_total) FROM {view}") == raw_total
    assert scalar(reader, "SELECT sum(price) FROM order_items") == raw_total


def test_freight_matches_raw(owner: Conn, reader: Conn) -> None:
    raw_total = scalar(owner, "SELECT sum(freight_value) FROM raw.order_items")
    for view in ["orders", "order_sellers", "order_categories"]:
        assert scalar(reader, f"SELECT sum(freight_total) FROM {view}") == raw_total
    assert scalar(reader, "SELECT sum(freight_value) FROM order_items") == raw_total


def test_payments_match_raw(owner: Conn, reader: Conn) -> None:
    raw_total = scalar(owner, "SELECT sum(payment_value) FROM raw.order_payments")
    assert raw_total == Decimal("16008872.12")  # audit control total
    assert scalar(reader, "SELECT sum(payment_total) FROM orders") == raw_total
    assert scalar(reader, "SELECT sum(payment_value) FROM order_payments") == raw_total


def test_joining_payments_to_items_would_double_count(owner: Conn) -> None:
    # Documents the trap the views avoid: a naive join inflates item revenue.
    naive = scalar(
        owner,
        """SELECT sum(i.price) FROM raw.order_items i
           JOIN raw.order_payments p USING (order_id)""",
    )
    assert naive > scalar(owner, "SELECT sum(price) FROM raw.order_items")


def test_order_counts_agree(reader: Conn) -> None:
    assert scalar(reader, "SELECT count(*) FROM orders") == 99_441
    assert scalar(reader, "SELECT sum(order_count) FROM customers") == 99_441
    ordered = scalar(reader, "SELECT count(*) FROM orders WHERE item_count > 0")
    assert scalar(reader, "SELECT count(DISTINCT order_id) FROM order_items") == ordered
    assert scalar(reader, "SELECT count(DISTINCT order_id) FROM order_sellers") == ordered
    assert scalar(reader, "SELECT count(DISTINCT order_id) FROM order_categories") == ordered


def test_units_sold_agree(reader: Conn) -> None:
    from_items = scalar(reader, "SELECT count(revenue) FROM order_items")
    assert from_items == 112_101
    assert scalar(reader, "SELECT sum(units_sold) FROM products") == from_items
    assert scalar(reader, "SELECT sum(units_sold) FROM sellers") == from_items


def test_customer_order_counts_do_not_use_per_order_ids(reader: Conn) -> None:
    # 99,441 per-order IDs, but only 96,096 people.
    assert scalar(reader, "SELECT count(*) FROM customers") == 96_096
    assert scalar(reader, "SELECT count(DISTINCT customer_unique_id) FROM orders") == 96_096
