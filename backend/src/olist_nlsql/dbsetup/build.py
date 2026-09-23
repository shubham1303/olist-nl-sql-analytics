"""Build the local database: roles, raw schema + load, analytics views, grants.

Every step is scripted and repeatable. ``build`` rebuilds the raw and analytics
schemas from scratch in one transaction, so a failed build leaves the previous
state intact. ``rebuild_views`` recreates only the analytics layer.
"""

from collections.abc import Callable
from importlib import resources
from pathlib import Path

import psycopg
from psycopg import sql

from olist_nlsql.dbsetup.dataset import SOURCE_FILES, verify
from olist_nlsql.dbsetup.env import OWNER_ROLE, READER_ROLE, LocalDb

# ADR 0002: every analytics_reader session gets these, independent of the app.
READER_STATEMENT_TIMEOUT = "10s"
READER_IDLE_IN_TRANSACTION_TIMEOUT = "30s"
READER_CONNECTION_LIMIT = 20

RAW_TABLES_SQL = "010_raw_tables.sql"
RAW_CONSTRAINTS_SQL = "020_raw_constraints.sql"
ANALYTICS_VIEWS_SQL = "030_analytics_views.sql"
GRANTS_SQL = "040_grants.sql"

Log = Callable[[str], None]


def _print(message: str) -> None:
    print(message, flush=True)


def read_sql(name: str) -> str:
    return resources.files("olist_nlsql.dbsetup").joinpath("sql", name).read_text("utf-8")


def _ensure_login_role(cur: psycopg.Cursor[tuple[object, ...]], role: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    verb = "ALTER" if cur.fetchone() else "CREATE"
    cur.execute(
        sql.SQL(
            "{verb} ROLE {role} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS PASSWORD {password}"
        ).format(verb=sql.SQL(verb), role=sql.Identifier(role), password=sql.Literal(password))
    )


def bootstrap(db: LocalDb, log: Log = _print) -> None:
    """Create/refresh roles and database-level privileges. Runs as the superuser."""
    log("bootstrap: roles and database privileges")
    database = sql.Identifier(db.dbname)
    owner = sql.Identifier(OWNER_ROLE)
    reader = sql.Identifier(READER_ROLE)
    with psycopg.connect(db.superuser_conninfo()) as conn, conn.cursor() as cur:
        _ensure_login_role(cur, OWNER_ROLE, db.owner_password)
        _ensure_login_role(cur, READER_ROLE, db.reader_password)
        statements: list[sql.SQL | sql.Composed] = [
            sql.SQL("ALTER ROLE {} CONNECTION LIMIT {}").format(
                reader, sql.Literal(READER_CONNECTION_LIMIT)
            ),
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(reader),
            sql.SQL("ALTER ROLE {} SET statement_timeout = {}").format(
                reader, sql.Literal(READER_STATEMENT_TIMEOUT)
            ),
            sql.SQL("ALTER ROLE {} SET idle_in_transaction_session_timeout = {}").format(
                reader, sql.Literal(READER_IDLE_IN_TRANSACTION_TIMEOUT)
            ),
            sql.SQL("ALTER ROLE {} SET search_path = analytics").format(reader),
            # Nobody gets implicit access: no PUBLIC connect or temp tables, and no
            # connecting to the default maintenance database either.
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database),
            sql.SQL("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC"),
            sql.SQL("GRANT CONNECT, CREATE ON DATABASE {} TO {}").format(database, owner),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, reader),
            sql.SQL("REVOKE ALL ON SCHEMA public FROM PUBLIC"),
        ]
        for statement in statements:
            cur.execute(statement)


def _load_raw(cur: psycopg.Cursor[tuple[object, ...]], data: Path, log: Log) -> None:
    for source in SOURCE_FILES:
        table = sql.Identifier("raw", source.table)
        copy_sql = sql.SQL("COPY {} FROM STDIN (FORMAT csv, HEADER true, ENCODING 'UTF8')")
        with (
            (data / source.filename).open("rb") as handle,
            cur.copy(copy_sql.format(table)) as copy,
        ):
            while chunk := handle.read(1 << 20):
                copy.write(chunk)
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(table))
        row = cur.fetchone()
        loaded = row[0] if row else 0
        if loaded != source.rows:
            raise RuntimeError(f"raw.{source.table}: loaded {loaded} rows, expected {source.rows}")
        log(f"  raw.{source.table}: {loaded:,} rows")


def _drop_analytics(cur: psycopg.Cursor[tuple[object, ...]]) -> None:
    cur.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
    cur.execute("DROP SCHEMA IF EXISTS analytics_internal CASCADE")


def _create_views(cur: psycopg.Cursor[tuple[object, ...]]) -> None:
    _drop_analytics(cur)
    cur.execute(read_sql(ANALYTICS_VIEWS_SQL))
    cur.execute(read_sql(GRANTS_SQL))


def build(db: LocalDb, data: Path, log: Log = _print) -> None:
    """Full rebuild of raw + analytics as olist_owner, in a single transaction."""
    verify(data)
    bootstrap(db, log)
    log("build: raw schema")
    with psycopg.connect(db.owner_conninfo()) as conn, conn.cursor() as cur:
        _drop_analytics(cur)
        cur.execute("DROP SCHEMA IF EXISTS raw CASCADE")
        cur.execute(read_sql(RAW_TABLES_SQL))
        _load_raw(cur, data, log)
        log("build: raw constraints")
        cur.execute(read_sql(RAW_CONSTRAINTS_SQL))
        cur.execute("ANALYZE")
        log("build: analytics views and grants")
        _create_views(cur)
    log("build: done")


def rebuild_views(db: LocalDb, log: Log = _print) -> None:
    """Recreate only the analytics views and grants (raw data untouched)."""
    log("views: analytics views and grants")
    with psycopg.connect(db.owner_conninfo()) as conn, conn.cursor() as cur:
        _create_views(cur)
    log("views: done")
