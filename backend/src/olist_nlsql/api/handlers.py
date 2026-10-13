"""Framework-free request handling for ``GET /status`` and ``POST /query`` (ADR 0004).

The local dev server (``local_app.py``) and the Phase 7 Lambda handler both turn their
transport's request into a ``Request``, call ``Api.handle`` and send back the
``Response``. Everything that matters for security and cost lives here, so it is tested
once:

- the shared access code, compared as a SHA-256 hash in constant time,
- the request limits: JSON object only, at most ``max_request_bytes``, exactly one
  ``question`` field (question length is checked by the pipeline),
- the mapping from pipeline status to HTTP status.

``/status`` is the warm-up probe from the Aurora resume spike: it runs ``SELECT 1``
and answers ``ready`` or ``resuming`` without waiting, so it always returns fast.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from olist_nlsql.config import Settings
from olist_nlsql.db import DatabaseResumingError, QueryExecutionError, QueryExecutor
from olist_nlsql.pipeline import NlSqlPipeline, PipelineResult, Status, to_dict

ACCESS_CODE_HEADER = "x-access-code"

# Pipeline outcomes the UI renders as an answer are 200; the rest say what went wrong.
_HTTP_STATUS: dict[Status, int] = {
    "answered": 200,
    "unanswerable": 200,
    "rejected": 200,
    "execution_failed": 200,
    "invalid_question": 400,
    "generation_failed": 502,
    "database_resuming": 503,
    "validator_error": 500,
}

# Fields of the pipeline result that are internal (per-attempt token counts) or repeated.
_PRIVATE_FIELDS = ("attempts",)


def hash_access_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Request:
    method: str
    path: str
    headers: Mapping[str, str]  # names lower-cased by the caller
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: dict[str, Any]
    headers: dict[str, str] = field(
        default_factory=lambda: {"content-type": "application/json", "cache-control": "no-store"}
    )
    # For metrics and logs only, never sent: route, outcome, model calls, timings.
    observation: dict[str, Any] = field(default_factory=dict)

    def json(self) -> bytes:
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")


def _error(status: int, code: str, message: str, route: str = "other") -> Response:
    return Response(
        status,
        {"error": {"code": code, "message": message}},
        observation={"route": route, "outcome": code},
    )


def _status(http: int, db: str) -> Response:
    return Response(http, {"db": db}, observation={"route": "status", "outcome": db})


def public_result(result: PipelineResult) -> dict[str, Any]:
    body = to_dict(result)
    for name in _PRIVATE_FIELDS:
        body.pop(name, None)
    return body


@dataclass
class Api:
    settings: Settings
    pipeline: NlSqlPipeline
    executor: QueryExecutor

    def __post_init__(self) -> None:
        if not self.settings.access_code_sha256:
            raise ValueError(
                "NLSQL_ACCESS_CODE_SHA256 is not set; the API refuses to run without an "
                "access code (ADR 0004). Create one with: python -m olist_nlsql.api hash-code"
            )

    def handle(self, request: Request) -> Response:
        routes = {"/status": ("GET", self._status), "/query": ("POST", self._query)}
        path = request.path.rstrip("/") or "/"
        route = routes.get(path)
        if route is None:
            return _error(404, "NOT_FOUND", f"No route {request.path}.")
        method, handler = route
        name = path.lstrip("/")
        if request.method.upper() != method:
            return _error(405, "METHOD_NOT_ALLOWED", f"{request.path} only accepts {method}.", name)
        if not self._authorised(request):
            return _error(401, "UNAUTHORIZED", "Missing or wrong access code.", name)
        return handler(request)

    def _authorised(self, request: Request) -> bool:
        code = request.headers.get(ACCESS_CODE_HEADER, "")
        expected = self.settings.access_code_sha256 or ""
        # compare_digest on equal-length hex digests: constant time, nothing leaks
        return bool(code) and hmac.compare_digest(hash_access_code(code), expected)

    def _status(self, _request: Request) -> Response:
        try:
            self.executor.execute("SELECT 1", max_rows=1)
        except DatabaseResumingError:
            return _status(200, "resuming")
        except QueryExecutionError:
            return _status(503, "unavailable")
        return _status(200, "ready")

    def _query(self, request: Request) -> Response:
        if len(request.body) > self.settings.max_request_bytes:
            return _error(
                413,
                "REQUEST_TOO_LARGE",
                f"The request body is limited to {self.settings.max_request_bytes} bytes.",
                "query",
            )
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return _error(
                415, "UNSUPPORTED_MEDIA_TYPE", "Send the request as application/json.", "query"
            )
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error(400, "INVALID_JSON", "The request body is not valid JSON.", "query")
        if not isinstance(payload, dict) or set(payload) != {"question"}:
            return _error(
                400,
                "INVALID_REQUEST",
                'The body must be a JSON object with only "question".',
                "query",
            )
        question = payload["question"]
        if not isinstance(question, str):
            return _error(400, "INVALID_REQUEST", '"question" must be a string.', "query")
        result = self.pipeline.ask(question)
        observation = {
            "route": "query",
            "outcome": result.status,
            "model_calls": len(result.attempts),
            "repair_attempted": result.repair_attempted,
            "total_ms": result.timings.total_ms,
            "model_ms": round(sum(a.model_ms for a in result.attempts), 2),
            "execution_ms": result.timings.execution_ms,
            "input_tokens": sum(a.input_tokens + a.cache_read_tokens for a in result.attempts),
            "output_tokens": sum(a.output_tokens for a in result.attempts),
        }
        return Response(_HTTP_STATUS[result.status], public_result(result), observation=observation)
