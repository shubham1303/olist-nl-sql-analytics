"""analytics_reader can read the curated views and nothing else (ADR 0002).

Each test uses a fresh connection so a failed statement cannot affect others.
"""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from psycopg import errors

from olist_nlsql.dbsetup.env import LocalDb
from tests.integration.helpers import Conn, row, scalar


@pytest.fixture
def conn(local_db: LocalDb) -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    with psycopg.connect(local_db.reader_conninfo()) as c:
        yield c


def test_reader_can_select_every_analytics_view(conn: Conn) -> None:
    views = [v for (v,) in conn.execute(
        "SELECT table_name FROM information_schema.views WHERE table_schema = 'analytics'"
    )]  # fmt: skip
    assert len(views) == 8
    for view in views:
        conn.execute(f"SELECT * FROM analytics.{view} LIMIT 1").fetchall()


def test_session_settings(conn: Conn) -> None:
    assert row(
        conn,
        """SELECT current_setting('default_transaction_read_only'),
                  current_setting('statement_timeout'),
                  current_setting('search_path'),
                  current_setting('transaction_read_only')""",
    ) == ("on", "10s", "analytics", "on")


def test_role_attributes(conn: Conn) -> None:
    assert row(
        conn,
        """SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolconnlimit
           FROM pg_roles WHERE rolname = 'analytics_reader'""",
    ) == (False, False, False, False, False, 20)


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT * FROM raw.orders LIMIT 1",
        "SELECT * FROM raw.geolocation LIMIT 1",
        "SELECT * FROM analytics_internal.product_category_map LIMIT 1",
    ],
)
def test_reader_cannot_read_hidden_schemas(conn: Conn, statement: str) -> None:
    with pytest.raises(errors.InsufficientPrivilege):
        conn.execute(statement)


VIEW_DML = [
    "INSERT INTO analytics.order_payments (order_id) VALUES ('x')",
    "UPDATE analytics.order_payments SET payment_value = 0",
    "DELETE FROM analytics.order_payments",
]

DDL_AND_TRUNCATE = [
    "TRUNCATE raw.orders",
    "CREATE TABLE analytics.t (x int)",
    "CREATE TABLE public.t (x int)",
    "CREATE TEMP TABLE t (x int)",
    "CREATE SCHEMA evil",
    "DROP VIEW analytics.orders",
    "ALTER VIEW analytics.orders RENAME TO o",
]


def _read_write(conn: Conn) -> None:
    # A session may turn read-only off; the other layers must still hold.
    conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")
    conn.commit()
    assert scalar(conn, "SELECT current_setting('transaction_read_only')") == "off"


@pytest.mark.parametrize("statement", DDL_AND_TRUNCATE)
def test_ddl_blocked_by_read_only_default(conn: Conn, statement: str) -> None:
    with pytest.raises(errors.ReadOnlySqlTransaction):
        conn.execute(statement)


@pytest.mark.parametrize("statement", DDL_AND_TRUNCATE)
def test_ddl_blocked_by_privileges_when_read_write(conn: Conn, statement: str) -> None:
    _read_write(conn)
    with pytest.raises(errors.InsufficientPrivilege):
        conn.execute(statement)


@pytest.mark.parametrize("read_write", [False, True], ids=["read_only", "read_write"])
@pytest.mark.parametrize("statement", VIEW_DML)
def test_dml_on_views_is_rejected(conn: Conn, statement: str, read_write: bool) -> None:
    # Multi-table views are not updatable, so PostgreSQL rejects DML while rewriting.
    if read_write:
        _read_write(conn)
    with pytest.raises(errors.ObjectNotInPrerequisiteState):
        conn.execute(statement)


def test_reader_holds_only_select_on_views(conn: Conn) -> None:
    # The privilege layer, checked directly: it must hold even for an updatable view.
    rows = conn.execute(
        """SELECT c.relname,
                  has_table_privilege('analytics_reader', c.oid, 'SELECT'),
                  has_table_privilege('analytics_reader', c.oid,
                                      'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')
           FROM pg_class c WHERE c.relnamespace = 'analytics'::regnamespace"""
    ).fetchall()
    assert len(rows) == 8
    assert all(can_select and not can_write for _, can_select, can_write in rows), rows


def test_statement_timeout_fires(conn: Conn) -> None:
    with pytest.raises(errors.QueryCanceled):
        conn.execute("SELECT pg_sleep(11)")


def test_wrong_password_is_rejected(local_db: LocalDb) -> None:
    conninfo = local_db.reader_conninfo().replace(
        f"password={local_db.reader_password}", "password=wrong"
    )
    assert "password=wrong" in conninfo
    with pytest.raises(psycopg.OperationalError, match="password authentication failed"):
        psycopg.connect(conninfo).close()


def test_reader_cannot_connect_to_maintenance_database(local_db: LocalDb) -> None:
    conninfo = local_db.reader_conninfo().replace(f"dbname={local_db.dbname}", "dbname=postgres")
    with pytest.raises(psycopg.OperationalError, match="permission denied"):
        psycopg.connect(conninfo).close()


def test_reader_cannot_grant_access_onward(conn: Conn) -> None:
    with pytest.raises(errors.ReadOnlySqlTransaction):
        conn.execute("GRANT SELECT ON analytics.orders TO PUBLIC")
    conn.rollback()
    # Read-write: without grant option PostgreSQL only warns; verify nothing was granted.
    _read_write(conn)
    conn.execute("GRANT SELECT ON analytics.orders TO PUBLIC")
    assert (
        scalar(conn, "SELECT has_table_privilege('public', 'analytics.orders', 'SELECT')") is False
    )
