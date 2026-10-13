"""API handlers and the local dev server, with a fake model and a scripted executor."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, get_args

import pytest

from olist_nlsql.api import Api, Request, hash_access_code
from olist_nlsql.api.handlers import _HTTP_STATUS
from olist_nlsql.api.local_app import FixedSqlModel, SimulatedResume, serve
from olist_nlsql.config import ConfigError, Settings, load_settings
from olist_nlsql.db import (
    ColumnInfo,
    DatabaseResumingError,
    QueryExecutionError,
    QueryResult,
)
from olist_nlsql.llm.fake import FakeModelClient, reply_json
from olist_nlsql.pipeline import NlSqlPipeline, Status
from olist_nlsql.sqlsafety import SqlValidator

CODE = "correct-horse-battery"
SQL = "SELECT SUM(revenue) AS revenue FROM orders"
REVENUE = QueryResult((ColumnInfo("revenue", "number"),), ((Decimal("13494400.74"),),), False)


@dataclass
class Executor:
    error: Exception | None = None
    executed: list[str] = field(default_factory=list)

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        self.executed.append(sql)
        if self.error is not None:
            raise self.error
        return REVENUE


def make_api(*replies: str, executor: Executor | None = None) -> tuple[Api, Executor]:
    settings = Settings(access_code_sha256=hash_access_code(CODE))
    executor = executor or Executor()
    model = FakeModelClient.of(*replies)
    pipeline = NlSqlPipeline(
        model, SqlValidator.from_catalog(settings=settings), executor, settings
    )
    return Api(settings, pipeline, executor), executor


def query(api: Api, body: Any, *, code: str = CODE, raw: bytes | None = None) -> Any:
    headers = {"content-type": "application/json", "x-access-code": code}
    data = raw if raw is not None else json.dumps(body).encode()
    return api.handle(Request("POST", "/query", headers, data))


def test_every_pipeline_status_has_an_http_status() -> None:
    assert set(_HTTP_STATUS) == set(get_args(Status))


def test_api_refuses_to_start_without_an_access_code() -> None:
    settings = Settings()
    pipeline = NlSqlPipeline(
        FakeModelClient.of(), SqlValidator.from_catalog(settings=settings), Executor(), settings
    )
    with pytest.raises(ValueError, match="ACCESS_CODE"):
        Api(settings, pipeline, Executor())


def test_access_code_setting_must_be_a_sha256_digest() -> None:
    digest = hash_access_code(CODE)
    assert load_settings({"NLSQL_ACCESS_CODE_SHA256": digest.upper()}).access_code_sha256 == digest
    assert load_settings({}).access_code_sha256 is None
    with pytest.raises(ConfigError, match="SHA-256"):
        load_settings({"NLSQL_ACCESS_CODE_SHA256": CODE})


@pytest.mark.parametrize("code", ["", "wrong-code", CODE.upper(), hash_access_code(CODE)])
def test_wrong_or_missing_code_is_401_and_nothing_runs(code: str) -> None:
    api, executor = make_api()  # no scripted replies: any model call would fail the test
    for request in (
        Request("GET", "/status", {"x-access-code": code}),
        Request("POST", "/query", {"x-access-code": code, "content-type": "application/json"}),
    ):
        response = api.handle(request)
        assert response.status == 401
        assert response.body["error"]["code"] == "UNAUTHORIZED"
    assert executor.executed == []


def test_unknown_routes_and_methods() -> None:
    api, _ = make_api()
    assert api.handle(Request("GET", "/admin", {"x-access-code": CODE})).status == 404
    assert api.handle(Request("GET", "/query", {"x-access-code": CODE})).status == 405
    assert api.handle(Request("POST", "/status", {"x-access-code": CODE})).status == 405


def test_status_reports_ready_resuming_or_unavailable() -> None:
    for error, status, db in (
        (None, 200, "ready"),
        (DatabaseResumingError("resuming"), 200, "resuming"),
        (QueryExecutionError("down"), 503, "unavailable"),
    ):
        api, executor = make_api(executor=Executor(error))
        response = api.handle(Request("GET", "/status", {"x-access-code": CODE}))
        assert (response.status, response.body) == (status, {"db": db})
        assert executor.executed == ["SELECT 1"]


def test_query_answers_with_columns_rows_and_sql() -> None:
    api, executor = make_api(reply_json(SQL, metrics_used=["revenue"]))
    response = query(api, {"question": "What was total revenue?"})
    assert response.status == 200
    body = response.body
    assert body["status"] == "answered"
    assert body["columns"] == [{"name": "revenue", "type": "number"}]
    assert body["rows"] == [["13494400.74"]]
    assert body["metrics_used"] == ["revenue"]
    assert body["validated_sql"].startswith("SELECT")
    assert "attempts" not in body  # per-attempt token counts stay internal
    assert len(executor.executed) == 1


@pytest.mark.parametrize(
    ("body", "raw", "status", "code"),
    [
        (None, b"{not json", 400, "INVALID_JSON"),
        (None, b"\xff\xfe", 400, "INVALID_JSON"),
        (["a list"], None, 400, "INVALID_REQUEST"),
        ({"question": "x", "sql": "DROP TABLE orders"}, None, 400, "INVALID_REQUEST"),
        ({}, None, 400, "INVALID_REQUEST"),
        ({"question": 42}, None, 400, "INVALID_REQUEST"),
        (None, b'{"question": "' + b"x" * 5000 + b'"}', 413, "REQUEST_TOO_LARGE"),
    ],
)
def test_malformed_requests_never_reach_the_model(
    body: Any, raw: bytes | None, status: int, code: str
) -> None:
    api, executor = make_api()
    response = query(api, body, raw=raw)
    assert (response.status, response.body["error"]["code"]) == (status, code)
    assert executor.executed == []


def test_query_needs_json_content_type() -> None:
    api, _ = make_api()
    request = Request(
        "POST", "/query", {"x-access-code": CODE, "content-type": "text/plain"}, b"{}"
    )
    assert api.handle(request).status == 415


def test_overlong_question_is_400_from_the_pipeline() -> None:
    api, _ = make_api()
    response = query(api, {"question": "x" * 501})
    assert response.status == 400
    assert response.body["status"] == "invalid_question"


def test_database_resuming_during_a_query_is_503() -> None:
    api, _ = make_api(reply_json(SQL), executor=Executor(DatabaseResumingError("resuming")))
    response = query(api, {"question": "What was total revenue?"})
    assert response.status == 503
    assert response.body["status"] == "database_resuming"
    assert response.body["error"]["code"] == "DATABASE_RESUMING"


def test_simulated_resume_fails_fast_until_the_time_has_passed() -> None:
    now = [100.0]
    executor = SimulatedResume(Executor(), seconds=20, clock=lambda: now[0])
    with pytest.raises(DatabaseResumingError):
        executor.execute("SELECT 1", max_rows=1)  # first touch starts the resume
    now[0] = 119.0
    with pytest.raises(DatabaseResumingError):
        executor.execute("SELECT 1", max_rows=1)
    now[0] = 120.0
    assert executor.execute("SELECT 1", max_rows=1) == REVENUE


def test_fixed_sql_model_answers_every_question_the_same() -> None:
    model = FixedSqlModel(SQL)
    first = model.complete(None)  # type: ignore[arg-type]
    assert json.loads(first.text)["sql"] == SQL
    assert model.complete(None).text == first.text  # type: ignore[arg-type]


@pytest.fixture
def server_url() -> Iterator[str]:
    settings = Settings(access_code_sha256=hash_access_code(CODE))
    executor = Executor()
    pipeline = NlSqlPipeline(
        FixedSqlModel(SQL), SqlValidator.from_catalog(settings=settings), executor, settings
    )
    server = serve(Api(settings, pipeline, executor), "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _http(url: str, data: bytes | None = None, code: str = CODE) -> tuple[int, Any]:
    headers = {"X-Access-Code": code, "Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers)  # noqa: S310 - test server
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - test server
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_local_server_round_trip(server_url: str) -> None:
    assert _http(f"{server_url}/status") == (200, {"db": "ready"})
    assert _http(f"{server_url}/status", code="nope")[0] == 401
    status, body = _http(f"{server_url}/query", json.dumps({"question": "Revenue?"}).encode())
    assert status == 200 and body["rows"] == [["13494400.74"]]
    status, body = _http(f"{server_url}/query", b"x" * 10_000)
    assert (status, body["error"]["code"]) == (413, "REQUEST_TOO_LARGE")


def test_local_server_binds_to_loopback_only() -> None:
    api, _ = make_api()
    with pytest.raises(ValueError, match="loopback"):
        serve(api, "0.0.0.0", 0)  # noqa: S104 - the point of the test
