"""Benchmark runs through an API: JSON back to typed results, cold starts, a real server."""

import datetime as dt
import json
import os
from decimal import Decimal
from typing import Any

import pytest

from olist_nlsql.config import Settings
from olist_nlsql.db import ColumnInfo
from olist_nlsql.evaluation import runner
from olist_nlsql.evaluation.benchmark import Benchmark
from olist_nlsql.evaluation.remote import RemoteApi, result_from_json
from tests.unit.test_api import CODE, server_url  # noqa: F401 - pytest fixture
from tests.unit.test_eval_runner import make_item

ANSWER: dict[str, Any] = {
    "question": "q",
    "status": "answered",
    "model_id": "us.anthropic.claude-sonnet-4-6",
    "prompt_version": "v2",
    "interpretation": "i",
    "assumptions": [],
    "metrics_used": ["revenue"],
    "generated_sql": "SELECT 1",
    "validated_sql": "SELECT 1 LIMIT 1001",
    "repair_attempted": True,
    "columns": [
        {"name": "month", "type": "date"},
        {"name": "at", "type": "timestamp"},
        {"name": "revenue", "type": "number"},
        {"name": "orders", "type": "integer"},
        {"name": "state", "type": "text"},
    ],
    "rows": [
        ["2018-01-01", "2018-01-02T03:04:05", "13494400.74", 7, "SP"],
        [None, None, None, None, None],
    ],
    "truncated": False,
    "warnings": [],
    "timings": {
        "model_generation_ms": 1500,
        "repair_generation_ms": 900,
        "execution_ms": 80,
        "total_ms": 2600,
    },
    "error": None,
}


def test_json_rows_become_typed_values() -> None:
    result = result_from_json(ANSWER)
    assert result.columns[2] == ColumnInfo("revenue", "number")
    assert result.rows[0] == (
        dt.date(2018, 1, 1),
        dt.datetime(2018, 1, 2, 3, 4, 5),
        Decimal("13494400.74"),
        7,
        "SP",
    )
    assert result.rows[1] == (None, None, None, None, None)
    assert result.repair_attempted and [a.kind for a in result.attempts] == ["generation", "repair"]
    assert result.generated_sql == "SELECT 1"


class Server:
    def __init__(self, replies: list[tuple[int, dict[str, Any]]]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, bytes | None]] = []

    def __call__(self, url: str, code: str, body: bytes | None) -> tuple[int, dict[str, Any]]:
        self.calls.append((url.rsplit("/", 1)[-1], body))
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


def api(server: Server) -> RemoteApi:
    return RemoteApi("https://api.example", CODE, fetch=server, sleep=lambda _: None)


def test_waits_through_a_cold_start() -> None:
    server = Server([(200, {"db": "resuming"}), (200, {"db": "resuming"}), (200, {"db": "ready"})])
    api(server).wait_until_ready()
    assert [c[0] for c in server.calls] == ["status", "status", "status"]


def test_wrong_code_stops_the_run() -> None:
    with pytest.raises(ValueError, match="access code"):
        api(Server([(401, {"error": {"code": "UNAUTHORIZED"}})])).wait_until_ready()


def test_query_that_meets_a_resume_is_asked_again() -> None:
    server = Server(
        [
            (503, {**ANSWER, "status": "database_resuming"}),
            (200, {"db": "ready"}),
            (200, ANSWER),
        ]
    )
    result = api(server).ask("q")
    assert result.status == "answered"
    assert [c[0] for c in server.calls] == ["query", "status", "query"]
    assert json.loads(server.calls[0][1] or b"{}") == {"question": "q"}


def test_only_https_or_the_local_app() -> None:
    with pytest.raises(ValueError, match="https"):
        RemoteApi("http://api.example", CODE)
    RemoteApi("http://127.0.0.1:8000", CODE)


def test_runner_over_a_real_local_server(server_url: str) -> None:  # noqa: F811
    remote = RemoteApi(server_url, CODE)
    remote.wait_until_ready()
    record = runner.run(
        Benchmark("dev", (make_item("dev-001"),)), remote=remote, settings=Settings()
    )
    item = record.items[0]
    assert item.status == "answered" and item.correct is True
    assert record.model_id == "fake (--fake-sql)"
    assert record.model_settings == {"via_api": server_url}


def test_cli_needs_the_access_code_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from olist_nlsql.evaluation.__main__ import main

    monkeypatch.delenv("NLSQL_API_ACCESS_CODE", raising=False)
    monkeypatch.setattr(
        os, "environ", {k: v for k, v in os.environ.items() if k != "NLSQL_API_ACCESS_CODE"}
    )
    assert main(["run", "--split", "dev", "--api-url", "https://api.example", "dev-001"]) == 2
