"""The query-execution contract shared by the local and AWS backends.

Implementations: ``PostgresExecutor`` (local, psycopg) now; a Data API executor in
Phase 7. Both must satisfy the same contract tests.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

# Logical result types, as consumed by chart selection (ADR 0007).
ResultType = Literal["integer", "number", "text", "date", "timestamp", "boolean", "unknown"]


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    name: str
    type: ResultType


@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: tuple[ColumnInfo, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool  # True when more than max_rows rows were available


class QueryExecutionError(Exception):
    """The database rejected or failed the statement."""


class QueryTimeoutError(QueryExecutionError):
    """The statement exceeded the database statement timeout."""


class QueryExecutor(Protocol):
    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        """Run one read-only statement and return at most ``max_rows`` rows."""
        ...
