"""The whole pipeline against the real database, with a scripted (fake) model.

question -> fake model -> validator -> analytics_reader -> PostgreSQL -> result.

The SQL is scripted here, so this only tests the wiring, not how good the
model is at writing SQL (Phase 4 covers that).
"""

import json
from decimal import Decimal

import pytest

from olist_nlsql.cli import main
from olist_nlsql.config import Settings
from olist_nlsql.db.postgres import PostgresExecutor
from olist_nlsql.llm.fake import FakeModelClient, reply_json
from olist_nlsql.pipeline import NlSqlPipeline, PipelineResult
from olist_nlsql.sqlsafety import SqlValidator

SETTINGS = Settings()
VALIDATOR = SqlValidator.from_catalog(settings=SETTINGS)


def ask(
    executor: PostgresExecutor, question: str, *sql: str, **reply: object
) -> tuple[PipelineResult, FakeModelClient]:
    model = FakeModelClient.of(*(reply_json(s, **reply) for s in sql))  # type: ignore[arg-type]
    return NlSqlPipeline(model, VALIDATOR, executor, SETTINGS).ask(question), model


def total(result: PipelineResult, column: int) -> Decimal:
    return sum((Decimal(str(r[column])) for r in result.rows if r[column] is not None), Decimal(0))


def test_revenue_in_a_year(executor: PostgresExecutor) -> None:
    result, _ = ask(
        executor,
        "What was merchandise revenue in 2017?",
        "SELECT SUM(revenue) AS revenue FROM orders "
        "WHERE purchase_date >= DATE '2017-01-01' AND purchase_date < DATE '2018-01-01'",
        metrics_used=["revenue"],
    )
    assert result.status == "answered"
    assert result.rows == ((Decimal("6108492.27"),),)
    assert result.metrics_used == ("revenue",)


def test_late_delivery_rate(executor: PostgresExecutor) -> None:
    result, _ = ask(
        executor,
        "What is the late delivery rate?",
        "SELECT (COUNT(*) FILTER (WHERE is_late))::numeric / NULLIF(COUNT(is_late), 0) AS late_rate FROM orders",
    )
    assert result.status == "answered"
    (rate,) = result.rows[0]
    assert abs(Decimal(str(rate)) - Decimal(6534) / Decimal(96470)) < Decimal("1e-12")


def test_top_categories(executor: PostgresExecutor) -> None:
    result, _ = ask(
        executor,
        "Top 3 categories by revenue",
        "SELECT product_category, SUM(revenue) AS revenue FROM order_items "
        "GROUP BY product_category ORDER BY revenue DESC NULLS LAST LIMIT 3",
    )
    assert [r[0] for r in result.rows] == ["health_beauty", "watches_gifts", "bed_bath_table"]
    assert [c.name for c in result.columns] == ["product_category", "revenue"]


def test_seller_ranking_with_threshold(executor: PostgresExecutor) -> None:
    result, _ = ask(
        executor,
        "Best-rated sellers with at least 20 delivered orders",
        "SELECT seller_id, AVG(review_score) AS avg_score FROM order_sellers GROUP BY seller_id "
        "HAVING COUNT(*) FILTER (WHERE is_delivered) >= 20 ORDER BY avg_score DESC LIMIT 5",
        assumptions=["Assuming 'best-rated' means highest average review score."],
    )
    assert result.status == "answered" and result.row_count == 5
    assert result.assumptions == ("Assuming 'best-rated' means highest average review score.",)


def test_repeat_customer_rate(executor: PostgresExecutor) -> None:
    from olist_nlsql.catalog import load_catalog

    metric = next(m for m in load_catalog().metrics if m.name == "repeat_customer_rate")
    result, _ = ask(executor, "What share of customers came back?", metric.sql())
    (rate,) = result.rows[0]
    assert abs(Decimal(str(rate)) - Decimal(2801) / Decimal(93358)) < Decimal("1e-12")


def test_join_and_group_by(executor: PostgresExecutor) -> None:
    result, _ = ask(
        executor,
        "Health and beauty revenue by customer state",
        "SELECT o.customer_state, SUM(i.revenue) AS revenue FROM orders o "
        "JOIN order_items i ON o.order_id = i.order_id WHERE i.product_category = 'health_beauty' "
        "GROUP BY o.customer_state ORDER BY revenue DESC NULLS LAST",
    )
    assert result.status == "answered" and result.rows[0][0] == "SP"
    assert total(result, 1) == Decimal("1255695.13")


def test_monthly_orders_with_time_filter(executor: PostgresExecutor) -> None:
    result, _ = ask(
        executor,
        "Monthly orders in 2017",
        "SELECT purchase_month, COUNT(*) AS orders FROM orders WHERE purchase_date BETWEEN "
        "'2017-01-01' AND '2017-12-31' GROUP BY purchase_month ORDER BY purchase_month",
    )
    assert result.row_count == 12 and result.rows[0][1] == 800
    assert [c.type for c in result.columns] == ["date", "integer"]


def test_invalid_first_query_is_repaired(executor: PostgresExecutor) -> None:
    result, model = ask(
        executor,
        "Revenue by category",
        "SELECT i.product_category, SUM(o.revenue) FROM orders o JOIN order_items i ON o.order_id = i.order_id GROUP BY 1",
        "SELECT product_category, SUM(revenue) AS revenue FROM order_items GROUP BY product_category",
    )
    assert result.status == "answered" and result.answer_source == "repair"
    assert len(model.requests) == 2
    assert total(result, 1) == Decimal("13494400.74")


def test_both_attempts_invalid(executor: PostgresExecutor) -> None:
    result, model = ask(
        executor,
        "Customer lifetime revenue",
        "SELECT customer_unique_id, total_revenue FROM customers",
        "SELECT seller_id, total_revenue FROM sellers",
    )
    assert result.status == "rejected" and len(model.requests) == 2
    assert result.error is not None and result.error.code == "UNAPPROVED_RELATION"
    assert result.rows == ()


def test_database_execution_failure(executor: PostgresExecutor) -> None:
    result, model = ask(executor, "Divide by zero", "SELECT 1 / 0 AS impossible")
    assert result.status == "execution_failed" and len(model.requests) == 1
    assert result.error is not None and "division by zero" in result.error.message
    assert result.validated_sql is not None


def test_truncation(executor: PostgresExecutor) -> None:
    result, _ = ask(executor, "List orders", "SELECT order_id FROM orders ORDER BY order_id")
    assert result.row_count == SETTINGS.max_result_rows and result.truncated


def test_cli_json_with_fake_sql(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["ask", "How many orders?", "--json", "--fake-sql", "SELECT COUNT(*) AS orders FROM orders"]
    )
    data = json.loads(capsys.readouterr().out)
    assert code == 0 and data["status"] == "answered" and data["rows"] == [[99441]]
    assert (
        data["validated_sql"].startswith("SELECT") and "analytics.orders" in data["validated_sql"]
    )


def test_cli_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    main(["ask", "How many orders?", "--fake-sql", "SELECT COUNT(*) AS orders FROM orders"])
    out = capsys.readouterr().out
    for label in (
        "Question:",
        "Status:         answered",
        "Validated SQL (executed):",
        "Result: 1 rows",
        "Timings (ms):",
    ):
        assert label in out
