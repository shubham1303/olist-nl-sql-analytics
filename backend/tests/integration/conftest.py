"""Fixtures for tests that need the local database built by ``dbsetup build``.

Every test in this directory is marked ``integration`` and is excluded from the
default run. Run with ``uv run pytest -m integration``.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from olist_nlsql.catalog import Catalog, load_catalog
from olist_nlsql.db.postgres import PostgresExecutor
from olist_nlsql.dbsetup.env import LocalDb, data_dir, load_dotenv

_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _HERE in Path(item.path).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def local_db() -> LocalDb:
    load_dotenv()
    return LocalDb.from_env()


@pytest.fixture(scope="session")
def owner(local_db: LocalDb) -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    """Connection as olist_owner, for inspecting raw data. Read-only by convention."""
    with psycopg.connect(local_db.owner_conninfo(), autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def reader(local_db: LocalDb) -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    """Connection as analytics_reader: what the application will use."""
    with psycopg.connect(local_db.reader_conninfo(), autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def executor(local_db: LocalDb) -> PostgresExecutor:
    return PostgresExecutor(local_db.reader_conninfo())


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog()


@pytest.fixture(scope="session")
def csv_dir() -> Path:
    return data_dir()
