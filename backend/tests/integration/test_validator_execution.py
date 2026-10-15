"""The validator against the real database.

* Every accepted query executes as analytics_reader exactly as the validator emits it.
* Fan-out rejections target real errors: executed anyway (validator bypassed), those
  queries return demonstrably inflated numbers.
* Write/escape attempts the validator rejects are ALSO rejected by the database role
  on its own, so the validator is never the only control (ADR 0002).
"""

from decimal import Decimal

import psycopg
import pytest

from olist_nlsql.catalog import load_catalog
from olist_nlsql.db.postgres import PostgresExecutor
from olist_nlsql.dbsetup.env import LocalDb
from olist_nlsql.sqlsafety import SqlValidator
from tests.integration.helpers import Conn, scalar
from tests.sql_cases import ACCEPTED, DATABASE_BLOCKED, REJECTED, Case

VALIDATOR = SqlValidator.from_catalog()
REJECTED_BY_ID = {c.id: c for c in REJECTED}
TRUE_REVENUE = Decimal("13494400.74")


@pytest.mark.parametrize("case", ACCEPTED, ids=lambda c: c.id)
def test_accepted_sql_executes(executor: PostgresExecutor, case: Case) -> None:
    result = VALIDATOR.validate(case.sql)
    assert result.ok and result.sql is not None
    executor.execute(result.sql, max_rows=1000)


def test_catalog_metrics_through_the_validator_match_direct_execution(reader: Conn) -> None:
    for metric in load_catalog().metrics:
        result = VALIDATOR.validate(metric.sql())
        assert result.ok and result.sql is not None, metric.name
        assert scalar(reader, result.sql) == scalar(reader, metric.sql()), metric.name


# fan-out rejections are real errors


def test_revenue_after_items_join_is_inflated(reader: Conn) -> None:
    inflated = scalar(reader, REJECTED_BY_ID["fanout_revenue_items"].sql)
    assert inflated > TRUE_REVENUE * Decimal("1.1")  # every multi-item order counted again


def test_revenue_after_payments_join_is_inflated(reader: Conn) -> None:
    assert scalar(reader, REJECTED_BY_ID["fanout_revenue_payments"].sql) > TRUE_REVENUE


def test_items_times_payments_inflates_both_sides(reader: Conn) -> None:
    sql = REJECTED_BY_ID["fanout_items_times_payments"].sql
    items_value, payments_value = reader.execute(sql).fetchone() or (None, None)
    assert items_value > scalar(reader, "SELECT SUM(price) FROM order_items")
    assert payments_value > scalar(reader, "SELECT SUM(payment_value) FROM order_payments")


def test_review_average_after_items_join_is_biased(reader: Conn) -> None:
    biased = scalar(reader, REJECTED_BY_ID["fanout_reviews_items"].sql)
    correct = scalar(reader, "SELECT AVG(review_score) FROM orders")
    assert round(biased, 4) != round(correct, 4)


def test_bridge_outcomes_overcount_orders(reader: Conn) -> None:
    overcounted = scalar(reader, REJECTED_BY_ID["bridge_late_count_ungrouped"].sql)
    assert overcounted > scalar(reader, "SELECT COUNT(*) FILTER (WHERE is_late) FROM orders")


def test_one_side_per_seller_average_equals_the_bridge_answer(reader: Conn) -> None:
    case = next(c for c in ACCEPTED if c.id == "one_side_avg_per_seller")
    joined = reader.execute(f"SELECT * FROM ({case.sql}) x ORDER BY seller_id").fetchall()
    bridge = reader.execute(
        "SELECT seller_id, AVG(review_score), COUNT(order_id) FROM order_sellers "
        "GROUP BY seller_id ORDER BY seller_id"
    ).fetchall()
    assert joined == bridge


def test_one_side_sum_per_seller_overstates_the_total(reader: Conn) -> None:
    sql = REJECTED_BY_ID["one_side_sum_per_seller"].sql
    per_seller = scalar(reader, f"SELECT SUM(x.sum) FROM ({sql}) x")
    assert per_seller > scalar(reader, "SELECT SUM(payment_total) FROM orders")


def test_nulls_last_keeps_an_empty_month_out_of_the_top(reader: Conn) -> None:
    # dev-012's mechanism: a 2018 month with no revenue orders has NULL revenue, which
    # PostgreSQL sorts first under DESC
    sql = (
        "SELECT purchase_month, SUM(revenue) AS revenue FROM analytics.orders "
        "WHERE purchase_month >= DATE '2018-01-01' GROUP BY purchase_month "
        "ORDER BY revenue DESC LIMIT 1"
    )
    as_written = reader.execute(sql).fetchone()
    assert as_written is not None and as_written[1] is None
    result = VALIDATOR.validate(sql)
    assert result.sql is not None
    validated = reader.execute(result.sql).fetchone()
    assert validated is not None and validated[1] == scalar(
        reader,
        "SELECT max(r) FROM (SELECT SUM(revenue) AS r FROM analytics.orders "
        "WHERE purchase_month >= DATE '2018-01-01' GROUP BY purchase_month) x",
    )


def test_previous_month_self_join_matches_lag(reader: Conn) -> None:
    case = next(c for c in ACCEPTED if c.id == "self_join_previous_month")
    result = VALIDATOR.validate(case.sql)
    assert result.sql is not None
    joined = reader.execute(f"SELECT * FROM ({result.sql}) x ORDER BY 1").fetchall()
    lagged = reader.execute(
        "SELECT * FROM (SELECT purchase_month, SUM(revenue) AS rev, "
        "LAG(SUM(revenue)) OVER (ORDER BY purchase_month) AS previous, "
        "LAG(purchase_month) OVER (ORDER BY purchase_month) AS previous_month "
        "FROM analytics.orders GROUP BY purchase_month) x "
        "WHERE previous_month = purchase_month - INTERVAL '1 month' ORDER BY 1"
    ).fetchall()
    assert joined == [row[:3] for row in lagged]


def test_safe_preaggregation_gives_the_true_answer(executor: PostgresExecutor) -> None:
    case = next(c for c in ACCEPTED if c.id == "preaggregate_payments_cte")
    result = VALIDATOR.validate(case.sql)
    assert result.sql is not None
    revenue, paid = executor.execute(result.sql, max_rows=10).rows[0]
    assert revenue == TRUE_REVENUE
    assert paid == Decimal("16008872.12")


# the database blocks what the validator blocks


@pytest.mark.parametrize("case_id", DATABASE_BLOCKED)
def test_database_rejects_it_even_without_the_validator(local_db: LocalDb, case_id: str) -> None:
    case = REJECTED_BY_ID[case_id]
    assert not VALIDATOR.validate(case.sql).ok
    with psycopg.connect(local_db.reader_conninfo()) as conn, pytest.raises(psycopg.Error):
        conn.execute(case.sql)
