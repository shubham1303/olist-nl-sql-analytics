"""AWS ``QueryExecutor`` over the RDS Data API, as analytics_reader (ADR 0001, 0002).

The Lambda stays outside the VPC and never holds a database driver or connection. Each
call is one ``ExecuteStatement`` with the reader's Secrets Manager secret, so the role's
own settings apply: read-only transactions, a 10 s statement timeout and search_path
``analytics``.

Matches ``PostgresExecutor`` (same contract tests):
- the same logical column types and Python values (Decimal, date, datetime, int, bool),
- at most ``max_rows`` rows plus a truncation flag. The Data API has no cursor, so the
  statement is wrapped in ``SELECT * FROM (...) LIMIT max_rows + 1``, which also keeps
  responses under its 1 MiB cap,
- timeouts as ``QueryTimeoutError``, and a paused cluster as ``DatabaseResumingError``
  without retrying: resuming takes 20-90 s, longer than a request may wait
  (docs/spikes/aurora-resume.md).
"""

import datetime as dt
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Protocol, cast

from olist_nlsql.db.executor import (
    ColumnInfo,
    DatabaseResumingError,
    QueryExecutionError,
    QueryResult,
    QueryTimeoutError,
    ResultType,
)

# Data API columnMetadata.typeName -> logical result types.
_TYPES_BY_NAME: dict[str, ResultType] = {
    "bool": "boolean",
    "int2": "integer",
    "int4": "integer",
    "int8": "integer",
    "serial": "integer",
    "bigserial": "integer",
    "float4": "number",
    "float8": "number",
    "numeric": "number",
    "text": "text",
    "varchar": "text",
    "bpchar": "text",
    "name": "text",
    "date": "date",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",
}

_TIMEOUT_MARKERS = ("canceling statement due to statement timeout", "statement timeout")
_SHORT_OFFSET = re.compile(r"([+-]\d{2})$")  # '+00' -> '+00:00' for fromisoformat


class RdsDataClient(Protocol):
    def execute_statement(self, **kwargs: Any) -> Mapping[str, Any]: ...


def _value(field: Mapping[str, Any], type_: ResultType) -> object:
    if field.get("isNull"):
        return None
    if "booleanValue" in field:
        return bool(field["booleanValue"])
    if "longValue" in field:
        return int(field["longValue"])
    if "doubleValue" in field:
        return float(field["doubleValue"])
    text = field.get("stringValue")
    if text is None:
        return None
    if type_ == "number":
        return Decimal(text)
    if type_ == "date":
        return dt.date.fromisoformat(text)
    if type_ == "timestamp":
        return dt.datetime.fromisoformat(_SHORT_OFFSET.sub(r"\1:00", text))
    return str(text)


def _error_message(exc: Exception) -> tuple[str, str]:
    response = getattr(exc, "response", None)
    if isinstance(response, Mapping):
        error = response.get("Error", {})
        return str(error.get("Code", "")), str(error.get("Message", "")).strip()
    return type(exc).__name__, str(exc).strip()


def _boto3_client(region: str | None) -> RdsDataClient:
    import boto3
    from botocore.config import Config

    # Bounded latency: a short read timeout and one retry for transport errors.
    # DatabaseResumingException is not retried (see module docstring).
    client = boto3.client(
        "rds-data",
        region_name=region,
        config=Config(
            connect_timeout=5,
            read_timeout=20,
            retries={"mode": "standard", "total_max_attempts": 2},
        ),
    )
    return cast(RdsDataClient, client)


class DataApiExecutor:
    def __init__(
        self,
        cluster_arn: str,
        secret_arn: str,
        database: str,
        client: RdsDataClient | None = None,
        region: str | None = None,
    ) -> None:
        self._cluster_arn = cluster_arn
        self._secret_arn = secret_arn
        self._database = database
        self._client: RdsDataClient = client if client is not None else _boto3_client(region)

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        if max_rows < 1:
            raise ValueError("max_rows must be at least 1")
        body = sql.strip().rstrip(";").strip()
        # body is validator-regenerated SQL (ADR 0014); only the row limit is added here
        wrapped = f"SELECT * FROM (\n{body}\n) AS nlsql_result LIMIT {max_rows + 1}"  # noqa: S608
        try:
            response = self._client.execute_statement(
                resourceArn=self._cluster_arn,
                secretArn=self._secret_arn,
                database=self._database,
                sql=wrapped,
                includeResultMetadata=True,
            )
        except Exception as exc:  # botocore ClientError and transport errors
            code, message = _error_message(exc)
            if code == "DatabaseResumingException":
                raise DatabaseResumingError(message or "the database is resuming") from exc
            if code == "StatementTimeoutException" or any(
                marker in message.lower() for marker in _TIMEOUT_MARKERS
            ):
                raise QueryTimeoutError(message) from exc
            raise QueryExecutionError(f"{code}: {message}" if code else message) from exc

        metadata = response.get("columnMetadata") or []
        columns = tuple(
            ColumnInfo(
                str(c.get("label") or c.get("name") or ""),
                _TYPES_BY_NAME.get(str(c.get("typeName", "")).lower(), "unknown"),
            )
            for c in metadata
        )
        if not columns:
            raise QueryExecutionError("statement returned no result set")
        records = response.get("records") or []
        rows = tuple(
            tuple(_value(field, columns[i].type) for i, field in enumerate(record))
            for record in records
        )
        return QueryResult(columns=columns, rows=rows[:max_rows], truncated=len(rows) > max_rows)
