"""DataApiExecutor against a fake rds-data client: types, truncation and error mapping."""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from olist_nlsql.db import (
    ColumnInfo,
    DatabaseResumingError,
    QueryExecutionError,
    QueryTimeoutError,
)
from olist_nlsql.db.data_api import DataApiExecutor

CLUSTER = "arn:aws:rds:us-east-1:ACCOUNT:cluster:olist"
SECRET = "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:reader"  # noqa: S105 - an ARN


@dataclass
class FakeClient:
    response: Mapping[str, Any] = field(default_factory=dict)
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def execute_statement(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def client_error(code: str, message: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "ExecuteStatement")


def make(client: FakeClient) -> DataApiExecutor:
    return DataApiExecutor(CLUSTER, SECRET, "olist", client=client)


def meta(name: str, type_name: str) -> dict[str, str]:
    return {"name": name, "label": name, "typeName": type_name}


def test_types_and_values_match_the_local_executor() -> None:
    client = FakeClient(
        {
            "columnMetadata": [
                meta("order_id", "text"),
                meta("item_count", "int4"),
                meta("revenue", "numeric"),
                meta("is_late", "bool"),
                meta("purchase_month", "date"),
                meta("purchased_at", "timestamp"),
                meta("ratio", "float8"),
                meta("blob", "bytea"),
            ],
            "records": [
                [
                    {"stringValue": "e481f51cbdc54678b7cc49136f2d6af7"},
                    {"longValue": 1},
                    {"stringValue": "29.99"},
                    {"booleanValue": False},
                    {"stringValue": "2017-10-01"},
                    {"stringValue": "2017-10-02 10:56:33"},
                    {"doubleValue": 0.5},
                    {"isNull": True},
                ]
            ],
        }
    )
    result = make(client).execute("SELECT ...", max_rows=10)
    assert result.columns == (
        ColumnInfo("order_id", "text"),
        ColumnInfo("item_count", "integer"),
        ColumnInfo("revenue", "number"),
        ColumnInfo("is_late", "boolean"),
        ColumnInfo("purchase_month", "date"),
        ColumnInfo("purchased_at", "timestamp"),
        ColumnInfo("ratio", "number"),
        ColumnInfo("blob", "unknown"),
    )
    assert result.rows == (
        (
            "e481f51cbdc54678b7cc49136f2d6af7",
            1,
            Decimal("29.99"),
            False,
            dt.date(2017, 10, 1),
            dt.datetime(2017, 10, 2, 10, 56, 33),
            0.5,
            None,
        ),
    )
    assert result.truncated is False


def test_timestamptz_short_offset_parses() -> None:
    client = FakeClient(
        {
            "columnMetadata": [meta("at", "timestamptz")],
            "records": [[{"stringValue": "2018-01-02 03:04:05.5+00"}]],
        }
    )
    value = make(client).execute("SELECT now()", max_rows=1).rows[0][0]
    assert value == dt.datetime(2018, 1, 2, 3, 4, 5, 500000, tzinfo=dt.UTC)


def test_statement_is_wrapped_to_fetch_one_row_more_than_allowed() -> None:
    client = FakeClient({"columnMetadata": [meta("x", "int4")], "records": []})
    make(client).execute("SELECT x FROM t ORDER BY x;\n", max_rows=5)
    call = client.calls[0]
    assert call["resourceArn"] == CLUSTER and call["secretArn"] == SECRET
    assert call["database"] == "olist" and call["includeResultMetadata"] is True
    assert call["sql"] == "SELECT * FROM (\nSELECT x FROM t ORDER BY x\n) AS nlsql_result LIMIT 6"


def test_truncation_and_exact_limit() -> None:
    rows = [[{"longValue": i}] for i in range(6)]
    client = FakeClient({"columnMetadata": [meta("x", "int4")], "records": rows})
    result = make(client).execute("SELECT x", max_rows=5)
    assert len(result.rows) == 5 and result.truncated is True
    client.response = {"columnMetadata": [meta("x", "int4")], "records": rows[:5]}
    assert make(client).execute("SELECT x", max_rows=5).truncated is False


def test_empty_result_keeps_columns() -> None:
    client = FakeClient({"columnMetadata": [meta("seller_id", "varchar")], "records": []})
    result = make(client).execute("SELECT seller_id FROM sellers WHERE false", max_rows=5)
    assert result.columns == (ColumnInfo("seller_id", "text"),) and result.rows == ()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            client_error("DatabaseResumingException", "The database is resuming."),
            DatabaseResumingError,
        ),
        (
            client_error(
                "BadRequestException", "ERROR: canceling statement due to statement timeout"
            ),
            QueryTimeoutError,
        ),
        (client_error("StatementTimeoutException", "Request timed out"), QueryTimeoutError),
        (
            client_error("BadRequestException", 'ERROR: relation "raw.orders" does not exist'),
            QueryExecutionError,
        ),
        (client_error("ForbiddenException", "not authorized"), QueryExecutionError),
        (
            EndpointConnectionError(endpoint_url="https://rds-data.us-east-1.amazonaws.com"),
            QueryExecutionError,
        ),
    ],
)
def test_errors_map_to_executor_errors(error: Exception, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        make(FakeClient(error=error)).execute("SELECT 1", max_rows=1)


def test_resuming_is_not_a_generic_failure_and_is_not_retried() -> None:
    client = FakeClient(error=client_error("DatabaseResumingException", "resuming"))
    with pytest.raises(DatabaseResumingError):
        make(client).execute("SELECT 1", max_rows=1)
    assert len(client.calls) == 1


def test_no_result_set_is_an_error() -> None:
    with pytest.raises(QueryExecutionError, match="no result set"):
        make(FakeClient({"numberOfRecordsUpdated": 0})).execute("SELECT 1", max_rows=1)


def test_max_rows_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_rows"):
        make(FakeClient()).execute("SELECT 1", max_rows=0)
