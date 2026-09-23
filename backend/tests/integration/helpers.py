from typing import Any

import psycopg

Conn = psycopg.Connection[tuple[Any, ...]]


def scalar(conn: Conn, sql: str) -> Any:
    return row(conn, sql)[0]


def row(conn: Conn, sql: str) -> tuple[Any, ...]:
    result = conn.execute(sql).fetchone()
    assert result is not None, sql
    return result
