"""Read-only query execution behind a driver-independent interface (ADR 0001)."""

from olist_nlsql.db.executor import (
    ColumnInfo,
    QueryExecutionError,
    QueryExecutor,
    QueryResult,
    QueryTimeoutError,
    ResultType,
)

__all__ = [
    "ColumnInfo",
    "QueryExecutionError",
    "QueryExecutor",
    "QueryResult",
    "QueryTimeoutError",
    "ResultType",
]
