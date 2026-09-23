"""Concrete records whose values were read from the source CSVs and checked by hand."""

import datetime as dt
from decimal import Decimal

from tests.integration.helpers import Conn, row, scalar


def test_first_order_in_the_orders_csv(reader: Conn) -> None:
    # CSV: purchased 2017-10-02 10:56:33, delivered 2017-10-10 21:25:13, estimated 2017-10-18;
    # one item at 29.99 + 8.72 freight; paid 38.71 in three records (18.12 + 2.00 + 18.59).
    assert row(
        reader,
        """SELECT order_status, delivery_status, is_late, delivery_delay_days, delivery_days,
                  item_price_total, freight_total, revenue, payment_total, payment_count,
                  review_score, customer_unique_id
           FROM orders WHERE order_id = 'e481f51cbdc54678b7cc49136f2d6af7'""",
    ) == (
        "delivered", "early", False, -8, Decimal("8.44"),
        Decimal("29.99"), Decimal("8.72"), Decimal("29.99"), Decimal("38.71"), 3,
        4, "7c396fd4830fd04220f754e42b4e5bff",
    )  # fmt: skip


def test_order_with_29_payment_records_is_one_row(reader: Conn) -> None:
    order = "fa65dad1b0e818e3ccc5cb0e39231352"
    assert scalar(reader, f"SELECT count(*) FROM orders WHERE order_id = '{order}'") == 1
    assert row(
        reader,
        f"""SELECT payment_count, payment_total, revenue, order_total_value, item_count
            FROM orders WHERE order_id = '{order}'""",
    ) == (29, Decimal("457.99"), Decimal("392.55"), Decimal("457.99"), 1)
    assert scalar(reader, f"SELECT count(*) FROM order_payments WHERE order_id = '{order}'") == 29


def test_order_with_21_items(reader: Conn) -> None:
    # Freight (164.37) exceeds the item value (31.80): freight must stay out of revenue.
    order = "8272b63d03f5f79c56e9e4120aec44ef"
    assert row(
        reader,
        f"""SELECT item_count, product_count, seller_count, revenue, freight_total
            FROM orders WHERE order_id = '{order}'""",
    ) == (21, 3, 1, Decimal("31.80"), Decimal("164.37"))
    assert scalar(reader, f"SELECT count(*) FROM order_items WHERE order_id = '{order}'") == 21
    assert scalar(reader, f"SELECT count(*) FROM order_sellers WHERE order_id = '{order}'") == 1


def test_latest_review_wins_for_multi_review_order(reader: Conn) -> None:
    # Reviews answered 2018-03-06 (3), 2018-03-21 (3), 2018-03-30 (4): latest is 4.
    assert row(
        reader,
        """SELECT review_count, review_score, review_answered_at
           FROM orders WHERE order_id = '03c939fd7fd3b38f8485a0f95798f1f6'""",
    ) == (3, 4, dt.datetime(2018, 3, 30, 0, 29, 9))


def test_person_with_17_customer_ids_is_one_customer(reader: Conn) -> None:
    person = "8d50f5eadf50201ccdcedfb9e2ac8455"
    assert (
        scalar(reader, f"SELECT count(*) FROM customers WHERE customer_unique_id = '{person}'") == 1
    )
    assert row(
        reader,
        f"""SELECT order_count, delivered_order_count, is_repeat_customer
            FROM customers WHERE customer_unique_id = '{person}'""",
    ) == (17, 15, True)


def test_unavailable_orders_have_no_revenue(reader: Conn) -> None:
    assert row(
        reader,
        """SELECT count(*), count(revenue), bool_or(is_revenue_order)
           FROM orders WHERE order_status IN ('canceled', 'unavailable')""",
    ) == (1_234, 0, False)


def test_canceled_orders_with_items_keep_gross_value(reader: Conn) -> None:
    # 461 canceled orders still have items: gross value is visible, revenue is not.
    n, gross = row(
        reader,
        "SELECT count(*), sum(item_price_total) FROM orders WHERE is_canceled AND item_count > 0",
    )
    assert n == 461
    assert gross > 0


def test_delivery_status_distribution(reader: Conn) -> None:
    assert dict(reader.execute("SELECT delivery_status, count(*) FROM orders GROUP BY 1")) == {
        "early": 88_644,
        "on_time": 1_292,
        "late": 6_534,
        "not_delivered": 2_963,
        "missing_delivery_date": 8,
    }


def test_on_time_uses_calendar_dates(reader: Conn) -> None:
    # Delivered later in the day of the estimate is on time, not late.
    n = scalar(
        reader,
        """SELECT count(*) FROM orders
           WHERE delivery_status = 'on_time' AND delivered_to_customer_at::time > '00:00'""",
    )
    assert n > 0
    assert (
        scalar(reader, "SELECT count(*) FROM orders WHERE is_late AND delivery_delay_days <= 0")
        == 0
    )
