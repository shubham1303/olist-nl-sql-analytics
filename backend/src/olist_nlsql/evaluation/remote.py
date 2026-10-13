"""Ask benchmark questions through a deployed API instead of the in-process pipeline.

Used for the Phase 7 smoke subset: ``run --split dev --api-url https://... dev-001 ...``
checks the whole deployed path (API Gateway, Lambda, Bedrock, Data API, Aurora). The
access code comes from ``NLSQL_API_ACCESS_CODE``, never from the command line.

The public API doesn't return per-attempt details, so the rebuilt ``PipelineResult``
has one attempt per model call it can infer (generation, plus repair when reported)
and no token counts. Rows come back as JSON and are converted back to Python types by
column type, so the comparator sees Decimals and dates as it does locally.
"""

import datetime as dt
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from decimal import Decimal
from typing import Any, cast

from olist_nlsql.db import ColumnInfo, ResultType
from olist_nlsql.pipeline import Attempt, PipelineError, PipelineResult, Status, Timings

RESUME_LIMIT_S = 240

Fetch = Callable[[str, str, bytes | None], tuple[int, dict[str, Any]]]


def _http(url: str, code: str, body: bytes | None) -> tuple[int, dict[str, Any]]:
    headers = {"X-Access-Code": code, "Content-Type": "application/json"}
    request = urllib.request.Request(url, data=body, headers=headers)  # noqa: S310 - https URL from the CLI
    try:
        with urllib.request.urlopen(request, timeout=40) as response:  # noqa: S310
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def _cell(value: object, type_: ResultType) -> object:
    if value is None or not isinstance(value, str):
        return value
    if type_ in ("number", "integer"):
        return Decimal(value)
    if type_ == "date":
        return dt.date.fromisoformat(value)
    if type_ == "timestamp":
        return dt.datetime.fromisoformat(value)
    return value


def result_from_json(body: dict[str, Any]) -> PipelineResult:
    columns = tuple(
        ColumnInfo(str(c["name"]), cast(ResultType, c["type"])) for c in body.get("columns", [])
    )
    rows = tuple(
        tuple(_cell(v, columns[i].type) for i, v in enumerate(row)) for row in body.get("rows", [])
    )
    t = body.get("timings") or {}
    attempts = [
        Attempt(
            "generation", float(t.get("model_generation_ms") or 0), sql=body.get("generated_sql")
        )
    ]
    if body.get("repair_attempted"):
        attempts.append(
            Attempt(
                "repair", float(t.get("repair_generation_ms") or 0), sql=body.get("generated_sql")
            )
        )
    error = body.get("error")
    return PipelineResult(
        question=str(body.get("question", "")),
        status=cast(Status, body["status"]),
        model_id=str(body.get("model_id", "unknown")),
        prompt_version=str(body.get("prompt_version", "unknown")),
        attempts=tuple(attempts),
        timings=Timings(
            prompt_build_ms=0.0,
            model_generation_ms=float(t.get("model_generation_ms") or 0),
            repair_generation_ms=t.get("repair_generation_ms"),
            validation_ms=float(t.get("validation_ms") or 0),
            execution_ms=t.get("execution_ms"),
            total_ms=float(t.get("total_ms") or 0),
        ),
        interpretation=body.get("interpretation"),
        assumptions=tuple(body.get("assumptions") or ()),
        metrics_used=tuple(body.get("metrics_used") or ()),
        validated_sql=body.get("validated_sql"),
        columns=columns,
        rows=rows,
        truncated=bool(body.get("truncated")),
        warnings=tuple(body.get("warnings") or ()),
        error=PipelineError(error["stage"], error["code"], error["message"]) if error else None,
    )


class RemoteApi:
    """Duck-types ``NlSqlPipeline.ask`` for the runner."""

    def __init__(
        self,
        base_url: str,
        access_code: str,
        fetch: Fetch = _http,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not base_url.startswith("https://") and not base_url.startswith("http://127.0.0.1"):
            raise ValueError("--api-url must be https (or the local app on 127.0.0.1)")
        self.base = base_url.rstrip("/")
        self.code = access_code
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.model_id = "remote"

    def wait_until_ready(self) -> None:
        """Poll /status like the UI does, through a cold start of the database."""
        deadline = self.clock() + RESUME_LIMIT_S
        while True:
            status, body = self.fetch(f"{self.base}/status", self.code, None)
            if status == 401:
                raise ValueError("the API rejected the access code (NLSQL_API_ACCESS_CODE)")
            if status == 200 and body.get("db") == "ready":
                return
            if self.clock() > deadline:
                raise RuntimeError(f"database not ready after {RESUME_LIMIT_S} s: {status} {body}")
            self.sleep(3)

    def ask(self, question: str) -> PipelineResult:
        payload = json.dumps({"question": question}).encode()
        status, body = self.fetch(f"{self.base}/query", self.code, payload)
        if status == 503 and body.get("status") == "database_resuming":
            self.wait_until_ready()
            status, body = self.fetch(f"{self.base}/query", self.code, payload)
        if "status" not in body:
            message = (body.get("error") or {}).get("message", f"HTTP {status}")
            raise RuntimeError(f"the API did not return a result: {message}")
        result = result_from_json(body)
        self.model_id = result.model_id
        return result
