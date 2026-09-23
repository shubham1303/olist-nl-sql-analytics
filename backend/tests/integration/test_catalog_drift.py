"""catalog.yaml and the live analytics views must describe exactly the same schema.

The catalog feeds both the model's schema context and the validator allowlist
(ADR 0005), so any drift here is a correctness or security bug.
"""

from olist_nlsql.catalog import Catalog
from tests.integration.helpers import Conn

# information_schema data_type -> catalog logical type
LOGICAL_TYPES = {
    "text": "text",
    "integer": "integer",
    "numeric": "numeric",
    "boolean": "boolean",
    "date": "date",
    "timestamp without time zone": "timestamp",
}


def live_columns(conn: Conn) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for table, column, data_type in conn.execute(
        """SELECT table_name, column_name, data_type FROM information_schema.columns
           WHERE table_schema = 'analytics' ORDER BY table_name, ordinal_position"""
    ):
        result.setdefault(table, {})[column] = data_type
    return result


def test_relations_match(reader: Conn, catalog: Catalog) -> None:
    assert set(live_columns(reader)) == {r.name for r in catalog.relations}


def test_columns_and_types_match(reader: Conn, catalog: Catalog) -> None:
    live = live_columns(reader)
    for relation in catalog.relations:
        documented = {c.name: c.type for c in relation.columns}
        actual = {
            name: LOGICAL_TYPES.get(t, f"unmapped:{t}") for name, t in live[relation.name].items()
        }
        assert actual == documented, relation.name


def test_column_order_matches(reader: Conn, catalog: Catalog) -> None:
    # Keeps SELECT * output and the model's schema context in the same order.
    live = live_columns(reader)
    for relation in catalog.relations:
        assert list(live[relation.name]) == [c.name for c in relation.columns], relation.name


def test_enumerated_values_are_exhaustive(reader: Conn, catalog: Catalog) -> None:
    for relation in catalog.relations:
        for column in relation.columns:
            if column.values is None:
                continue
            actual = {
                v
                for (v,) in reader.execute(
                    f"SELECT DISTINCT {column.name} FROM analytics.{relation.name}"
                    f" WHERE {column.name} IS NOT NULL"
                )
            }
            assert actual == set(column.values), f"{relation.name}.{column.name}"
