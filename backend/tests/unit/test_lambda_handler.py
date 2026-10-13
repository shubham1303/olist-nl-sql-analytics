"""Lambda handler with API Gateway HTTP API (payload 2.0) events, and the EMF record."""

import base64
import json
from collections.abc import Iterator
from typing import Any

import pytest

from olist_nlsql.api import lambda_handler
from olist_nlsql.api.metrics import NAMESPACE, emf_record
from olist_nlsql.llm.fake import reply_json
from tests.unit.test_api import CODE, SQL, make_api


def event(
    method: str, path: str, *, body: str | None = None, code: str = CODE, b64: bool = False
) -> dict[str, Any]:
    raw = body
    if body is not None and b64:
        raw = base64.b64encode(body.encode()).decode()
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "headers": {"X-Access-Code": code, "Content-Type": "application/json"},
        "requestContext": {"http": {"method": method, "path": path}, "stage": "$default"},
        "body": raw,
        "isBase64Encoded": b64,
    }


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    built, _ = make_api(reply_json(SQL))
    monkeypatch.setattr(lambda_handler, "_api", built)
    yield
    monkeypatch.setattr(lambda_handler, "_api", None)


def emitted(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert len(lines) == 1
    return dict(json.loads(lines[0]))


def test_status_event(api: None, capsys: pytest.CaptureFixture[str]) -> None:
    response = lambda_handler.handler(event("GET", "/status"), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"db": "ready"}
    assert response["headers"]["content-type"] == "application/json"
    assert response["isBase64Encoded"] is False
    record = emitted(capsys)
    assert (record["Route"], record["Outcome"], record["Requests"]) == ("status", "ready", 1)


@pytest.mark.parametrize("b64", [False, True])
def test_query_event(api: None, capsys: pytest.CaptureFixture[str], b64: bool) -> None:
    body = json.dumps({"question": "What was total revenue?"})
    response = lambda_handler.handler(event("POST", "/query", body=body, b64=b64), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["rows"] == [["13494400.74"]]
    record = emitted(capsys)
    assert (record["Route"], record["Outcome"]) == ("query", "answered")
    assert record["ModelCalls"] == 1 and "LatencyMs" in record and "ExecutionMs" in record


def test_wrong_code_is_401_and_counted(api: None, capsys: pytest.CaptureFixture[str]) -> None:
    response = lambda_handler.handler(event("GET", "/status", code="nope"), None)
    assert response["statusCode"] == 401
    record = emitted(capsys)
    assert (record["Route"], record["Outcome"], record["http_status"]) == (
        "status",
        "UNAUTHORIZED",
        401,
    )


def test_missing_configuration_fails_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(lambda_handler, "_api", None)
    for name in ("NLSQL_DB_CLUSTER_ARN", "NLSQL_DB_SECRET_ARN"):
        monkeypatch.delenv(name, raising=False)
    response = lambda_handler.handler(event("GET", "/status"), None)
    assert response["statusCode"] == 500
    assert json.loads(response["body"])["error"]["code"] == "INTERNAL_ERROR"
    assert "NLSQL_DB" not in response["body"]  # no internals leak to the client
    assert emitted(capsys)["Outcome"] == "INTERNAL_ERROR"


def test_emf_record_shape() -> None:
    record = emf_record(
        {
            "route": "query",
            "outcome": "rejected",
            "model_calls": 2,
            "repair_attempted": True,
            "total_ms": 4200.5,
            "execution_ms": None,
        },
        200,
        4300.0,
        now_ms=1,
    )
    directive = record["_aws"]["CloudWatchMetrics"][0]
    assert record["_aws"]["Timestamp"] == 1
    assert directive["Namespace"] == NAMESPACE
    assert directive["Dimensions"] == [["Route"], ["Route", "Outcome"]]
    names = {m["Name"] for m in directive["Metrics"]}
    assert names == {"Requests", "HandlerMs", "LatencyMs", "ModelCalls", "Repairs"}
    assert all(name in record for name in names)  # every declared metric has a value
    assert "ExecutionMs" not in record  # None is not a metric value
