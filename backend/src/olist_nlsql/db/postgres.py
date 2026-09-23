"""Local ``QueryExecutor`` over psycopg, connecting as analytics_reader."""

import psycopg
from psycopg import errors

from olist_nlsql.db.executor import (
    ColumnInfo,
    QueryExecutionError,
    QueryResult,
    QueryTimeoutError,
    ResultType,
)

# PostgreSQL type OIDs -> logical result types.
_TYPES_BY_OID: dict[int, ResultType] = {
    16: "boolean",
    20: "integer",  # int8
    21: "integer",  # int2
    23: "integer",  # int4
    700: "number",  # float4
    701: "number",  # float8
    1700: "number",  # numeric
    25: "text",
    1042: "text",  # bpchar
    1043: "text",  # varchar
    19: "text",  # name
    1082: "date",
    1114: "timestamp",
    1184: "timestamp",  # timestamptz
}


class PostgresExecutor:
    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        if max_rows < 1:
            raise ValueError("max_rows must be at least 1")
        try:
            with psycopg.connect(self._conninfo) as conn:
                # Defence in depth: the role already defaults to read-only (ADR 0002).
                conn.read_only = True
                # A server-side cursor transfers only max_rows + 1 rows, and DECLARE
                # accepts exactly one SELECT/VALUES statement.
                with conn.cursor(name="nlsql_query") as cur:
                    cur.execute(sql)
                    if cur.description is None:
                        raise QueryExecutionError("statement returned no result set")
                    columns = tuple(
                        ColumnInfo(d.name, _TYPES_BY_OID.get(d.type_code, "unknown"))
                        for d in cur.description
                    )
                    rows = cur.fetchmany(max_rows + 1)
                conn.rollback()
        except errors.QueryCanceled as exc:
            raise QueryTimeoutError(str(exc).strip()) from exc
        except psycopg.Error as exc:
            raise QueryExecutionError(str(exc).strip()) from exc
        return QueryResult(
            columns=columns,
            rows=tuple(tuple(row) for row in rows[:max_rows]),
            truncated=len(rows) > max_rows,
        )
