"""Source-data assumptions. If Olist data changes, these fail before any view is trusted.

Runs as olist_owner (the reader cannot see raw). Values were profiled on the
pinned dataset and cross-checked against an independent audit where noted.
"""

import datetime as dt
from decimal import Decimal

import pytest

from olist_nlsql.dbsetup.dataset import SOURCE_FILES, SourceFile
from tests.integration.helpers import Conn, row, scalar


@pytest.mark.parametrize("source", SOURCE_FILES, ids=lambda s: s.table)
def test_row_counts_match_manifest(owner: Conn, source: SourceFile) -> None:
    assert scalar(owner, f"SELECT count(*) FROM raw.{source.table}") == source.rows


EXPECTED_KEYS = {
    ("customers", "customers_pkey"),
    ("orders", "orders_pkey"),
    ("order_items", "order_items_pkey"),
    ("order_payments", "order_payments_pkey"),
    ("order_reviews", "order_reviews_review_order_key"),
    ("products", "products_pkey"),
    ("sellers", "sellers_pkey"),
    ("product_category_name_translation", "product_category_name_translation_pkey"),
}


def test_declared_keys_exist(owner: Conn) -> None:
    rows = owner.execute(
        """
        SELECT conrelid::regclass::text, conname FROM pg_constraint
        WHERE connamespace = 'raw'::regnamespace AND contype IN ('p', 'u')
        """
    ).fetchall()
    assert {(t.removeprefix("raw."), c) for t, c in rows} == EXPECTED_KEYS


def test_foreign_keys_hold(owner: Conn) -> None:
    # Declared (and therefore validated against every row) at load time.
    rows = owner.execute(
        """SELECT conrelid::regclass::text, confrelid::regclass::text FROM pg_constraint
           WHERE connamespace = 'raw'::regnamespace AND contype = 'f'"""
    ).fetchall()
    assert sorted(rows) == [
        ("raw.order_items", "raw.orders"),
        ("raw.order_items", "raw.products"),
        ("raw.order_items", "raw.sellers"),
        ("raw.order_payments", "raw.orders"),
        ("raw.order_reviews", "raw.orders"),
        ("raw.orders", "raw.customers"),
    ]


class TestCustomerIdentity:
    def test_customer_id_is_per_order(self, owner: Conn) -> None:
        orders, customer_ids = row(
            owner, "SELECT count(*), count(DISTINCT customer_id) FROM raw.orders"
        )
        assert orders == customer_ids == 99_441

    def test_customer_unique_id_is_not_unique(self, owner: Conn) -> None:
        assert (
            scalar(owner, "SELECT count(DISTINCT customer_unique_id) FROM raw.customers") == 96_096
        )

    def test_one_person_can_have_many_customer_ids(self, owner: Conn) -> None:
        n = scalar(
            owner,
            """SELECT count(*) FROM raw.customers
               WHERE customer_unique_id = '8d50f5eadf50201ccdcedfb9e2ac8455'""",
        )
        assert n == 17

    def test_some_people_ordered_from_several_states(self, owner: Conn) -> None:
        n = scalar(
            owner,
            """SELECT count(*) FROM (SELECT customer_unique_id FROM raw.customers
               GROUP BY 1 HAVING count(DISTINCT customer_state) > 1) s""",
        )
        assert n == 39


class TestFanOut:
    def test_multiple_items_per_order(self, owner: Conn) -> None:
        multi, max_items = row(
            owner,
            """SELECT count(*) FILTER (WHERE n > 1), max(n)
               FROM (SELECT count(*) n FROM raw.order_items GROUP BY order_id) s""",
        )
        assert (multi, max_items) == (9_803, 21)

    def test_multiple_sellers_per_order(self, owner: Conn) -> None:
        multi, max_sellers = row(
            owner,
            """SELECT count(*) FILTER (WHERE n > 1), max(n) FROM
               (SELECT count(DISTINCT seller_id) n FROM raw.order_items GROUP BY order_id) s""",
        )
        assert (multi, max_sellers) == (1_278, 5)

    def test_multiple_payments_per_order(self, owner: Conn) -> None:
        multi, max_payments = row(
            owner,
            """SELECT count(*) FILTER (WHERE n > 1), max(n)
               FROM (SELECT count(*) n FROM raw.order_payments GROUP BY order_id) s""",
        )
        assert (multi, max_payments) == (2_961, 29)

    def test_multiple_reviews_per_order(self, owner: Conn) -> None:
        multi, max_reviews, conflicting = row(
            owner,
            """SELECT count(*) FILTER (WHERE n > 1), max(n), count(*) FILTER (WHERE scores > 1)
               FROM (SELECT count(*) n, count(DISTINCT review_score) scores
                     FROM raw.order_reviews GROUP BY order_id) s""",
        )
        assert (multi, max_reviews, conflicting) == (547, 3, 202)

    def test_review_id_is_not_unique(self, owner: Conn) -> None:
        rows, ids, shared = row(
            owner,
            """SELECT count(*), count(DISTINCT review_id),
                      (SELECT count(*) FROM (SELECT review_id FROM raw.order_reviews
                       GROUP BY 1 HAVING count(*) > 1) s)
               FROM raw.order_reviews""",
        )
        assert (rows, ids, shared) == (99_224, 98_410, 789)


class TestMissingRelationships:
    """Left-join conditions, not errors. Audit values: 775 / 1 / 768."""

    def test_orders_without_items(self, owner: Conn) -> None:
        by_status: dict[str, int] = dict(
            owner.execute(
                """SELECT order_status, count(*) FROM raw.orders o
                   WHERE NOT EXISTS (SELECT 1 FROM raw.order_items i WHERE i.order_id = o.order_id)
                   GROUP BY 1"""
            ).fetchall()
        )
        assert sum(by_status.values()) == 775
        assert by_status == {
            "unavailable": 603,
            "canceled": 164,
            "created": 5,
            "invoiced": 2,
            "shipped": 1,
        }

    def test_orders_without_payments(self, owner: Conn) -> None:
        assert (
            scalar(
                owner,
                """SELECT count(*) FROM raw.orders o WHERE NOT EXISTS
                   (SELECT 1 FROM raw.order_payments p WHERE p.order_id = o.order_id)""",
            )
            == 1
        )

    def test_orders_without_reviews(self, owner: Conn) -> None:
        assert (
            scalar(
                owner,
                """SELECT count(*) FROM raw.orders o WHERE NOT EXISTS
                   (SELECT 1 FROM raw.order_reviews r WHERE r.order_id = o.order_id)""",
            )
            == 768
        )


class TestNullsAndDates:
    def test_order_timestamp_nulls(self, owner: Conn) -> None:
        assert row(
            owner,
            """SELECT count(*) FILTER (WHERE order_approved_at IS NULL),
                      count(*) FILTER (WHERE order_delivered_carrier_date IS NULL),
                      count(*) FILTER (WHERE order_delivered_customer_date IS NULL)
               FROM raw.orders""",
        ) == (160, 1_783, 2_965)

    def test_delivered_orders_missing_delivery_date(self, owner: Conn) -> None:
        n = scalar(
            owner,
            """SELECT count(*) FROM raw.orders
               WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL""",
        )
        assert n == 8

    def test_purchase_date_range(self, owner: Conn) -> None:
        first, last = row(
            owner,
            "SELECT min(order_purchase_timestamp), max(order_purchase_timestamp) FROM raw.orders",
        )
        assert first == dt.datetime(2016, 9, 4, 21, 15, 19)
        assert last == dt.datetime(2018, 10, 17, 17, 30, 18)

    def test_no_orders_in_november_2016(self, owner: Conn) -> None:
        n = scalar(
            owner,
            """SELECT count(*) FROM raw.orders
               WHERE order_purchase_timestamp >= '2016-11-01' AND order_purchase_timestamp < '2016-12-01'""",
        )
        assert n == 0

    def test_estimated_delivery_is_a_date(self, owner: Conn) -> None:
        n = scalar(
            owner,
            "SELECT count(*) FROM raw.orders WHERE order_estimated_delivery_date::time <> '00:00'",
        )
        assert n == 0

    def test_chronology_exceptions(self, owner: Conn) -> None:
        assert row(
            owner,
            """SELECT count(*) FILTER (WHERE order_delivered_carrier_date < order_approved_at),
                      count(*) FILTER (WHERE order_delivered_customer_date < order_delivered_carrier_date),
                      count(*) FILTER (WHERE order_delivered_customer_date < order_purchase_timestamp),
                      count(*) FILTER (WHERE order_approved_at < order_purchase_timestamp)
               FROM raw.orders""",
        ) == (1_359, 23, 0, 0)

    def test_order_statuses(self, owner: Conn) -> None:
        statuses = {s for (s,) in owner.execute("SELECT DISTINCT order_status FROM raw.orders")}
        assert statuses == {
            "approved", "canceled", "created", "delivered",
            "invoiced", "processing", "shipped", "unavailable",
        }  # fmt: skip


class TestNumericsAndFormats:
    def test_money_has_at_most_two_decimals(self, owner: Conn) -> None:
        assert row(
            owner,
            """SELECT (SELECT max(scale(price)) FROM raw.order_items),
                      (SELECT max(scale(freight_value)) FROM raw.order_items),
                      (SELECT max(scale(payment_value)) FROM raw.order_payments)""",
        ) == (2, 2, 2)

    def test_prices_positive_freight_non_negative(self, owner: Conn) -> None:
        min_price, min_freight = row(
            owner, "SELECT min(price), min(freight_value) FROM raw.order_items"
        )
        assert min_price == Decimal("0.85")
        assert min_freight == Decimal("0.00")

    def test_review_scores_are_one_to_five(self, owner: Conn) -> None:
        assert row(owner, "SELECT min(review_score), max(review_score) FROM raw.order_reviews") == (
            1,
            5,
        )

    def test_zip_prefixes_keep_leading_zeros(self, owner: Conn) -> None:
        bad = scalar(
            owner,
            """SELECT (SELECT count(*) FROM raw.customers WHERE customer_zip_code_prefix !~ '^[0-9]{5}$')
                    + (SELECT count(*) FROM raw.sellers WHERE seller_zip_code_prefix !~ '^[0-9]{5}$')""",
        )
        assert bad == 0
        assert (
            scalar(
                owner, "SELECT count(*) FROM raw.customers WHERE customer_zip_code_prefix LIKE '0%'"
            )
            > 0
        )

    def test_payment_types(self, owner: Conn) -> None:
        types: dict[str, int] = dict(
            owner.execute("SELECT payment_type, count(*) FROM raw.order_payments GROUP BY 1")
        )
        assert types == {
            "credit_card": 76_795, "boleto": 19_784, "voucher": 5_775,
            "debit_card": 1_529, "not_defined": 3,
        }  # fmt: skip


class TestCategories:
    def test_products_without_category(self, owner: Conn) -> None:
        assert (
            scalar(owner, "SELECT count(*) FROM raw.products WHERE product_category_name IS NULL")
            == 610
        )

    def test_untranslated_source_categories(self, owner: Conn) -> None:
        rows: dict[str, int] = dict(
            owner.execute(
                """SELECT p.product_category_name, count(*) FROM raw.products p
                   LEFT JOIN raw.product_category_name_translation t USING (product_category_name)
                   WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL
                   GROUP BY 1"""
            ).fetchall()
        )
        assert rows == {"portateis_cozinha_e_preparadores_de_alimentos": 10, "pc_gamer": 3}

    def test_translation_is_one_to_one(self, owner: Conn) -> None:
        assert row(
            owner,
            """SELECT count(*), count(DISTINCT product_category_name_english)
               FROM raw.product_category_name_translation""",
        ) == (71, 71)

    def test_source_translation_typo_exists(self, owner: Conn) -> None:
        # Corrected to 'home_comfort' in analytics_internal.product_category_map.
        english = scalar(
            owner,
            """SELECT product_category_name_english FROM raw.product_category_name_translation
               WHERE product_category_name = 'casa_conforto'""",
        )
        assert english == "home_confort"


def test_geolocation_is_loaded_but_messy(owner: Conn) -> None:
    rows, prefixes = row(
        owner, "SELECT count(*), count(DISTINCT geolocation_zip_code_prefix) FROM raw.geolocation"
    )
    assert (rows, prefixes) == (1_000_163, 19_015)
