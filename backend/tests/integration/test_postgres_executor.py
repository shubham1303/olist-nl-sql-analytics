"""The local QueryExecutor: typed columns, truncation and error mapping."""

import datetime as dt
from decimal import Decimal

import pytest

from olist_nlsql.db import ColumnInfo, QueryExecutionError, QueryTimeoutError
from olist_nlsql.db.postgres import PostgresExecutor


def test_columns_are_typed(executor: PostgresExecutor) -> None:
    result = executor.execute(
        """SELECT order_id, item_count, revenue, is_late, purchase_month, purchased_at
           FROM orders WHERE order_id = 'e481f51cbdc54678b7cc49136f2d6af7'""",
        max_rows=10,
    )
    assert result.columns == (
        ColumnInfo("order_id", "text"),
        ColumnInfo("item_count", "integer"),
        ColumnInfo("revenue", "number"),
        ColumnInfo("is_late", "boolean"),
        ColumnInfo("purchase_month", "date"),
        ColumnInfo("purchased_at", "timestamp"),
    )
    assert result.rows == (
        (
            "e481f51cbdc54678b7cc49136f2d6af7",
            1,
            Decimal("29.99"),
            False,
            dt.date(2017, 10, 1),
            dt.datetime(2017, 10, 2, 10, 56, 33),
        ),
    )
    assert result.truncated is False


def test_truncation(executor: PostgresExecutor) -> None:
    result = executor.execute("SELECT order_id FROM orders ORDER BY order_id", max_rows=5)
    assert len(result.rows) == 5
    assert result.truncated is True


def test_exact_row_limit_is_not_truncated(executor: PostgresExecutor) -> None:
    result = executor.execute("SELECT * FROM (VALUES (1), (2)) v(x)", max_rows=2)
    assert len(result.rows) == 2
    assert result.truncated is False


def test_empty_result_keeps_columns(executor: PostgresExecutor) -> None:
    result = executor.execute("SELECT seller_id FROM sellers WHERE false", max_rows=5)
    assert result.columns == (ColumnInfo("seller_id", "text"),)
    assert result.rows == ()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "DELETE FROM orders",
        "SELECT * FROM raw.orders",
        "SELECT * FROM no_such_view",
    ],
)
def test_rejected_statements_raise(executor: PostgresExecutor, sql: str) -> None:
    with pytest.raises(QueryExecutionError):
        executor.execute(sql, max_rows=5)


def test_timeout_is_distinguished(executor: PostgresExecutor) -> None:
    with pytest.raises(QueryTimeoutError):
        executor.execute("SELECT pg_sleep(11)", max_rows=1)


def test_max_rows_must_be_positive(executor: PostgresExecutor) -> None:
    with pytest.raises(ValueError, match="max_rows"):
        executor.execute("SELECT 1", max_rows=0)
