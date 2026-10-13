"""Local dev server for the API (Phase 6). Not deployed: AWS uses the Lambda handler.

Runs the shared ``Api`` behind the standard library's threaded HTTP server, against
local Docker Postgres and real Bedrock (or a fixed fake SQL answer for offline UI work).
It binds to loopback only. The Vite dev server proxies ``/api/*`` to it.

    python -m olist_nlsql.api serve [--simulate-resume 20] [--fake-sql "SELECT ..."]
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from olist_nlsql.api.handlers import Api, Request, Response
from olist_nlsql.db import DatabaseResumingError, QueryExecutor, QueryResult
from olist_nlsql.llm.client import ModelReply, ModelRequest
from olist_nlsql.llm.fake import reply_json

logger = logging.getLogger(__name__)


@dataclass
class SimulatedResume:
    """Acts like a paused Aurora cluster: the first call starts a resume, and every call
    fails fast with ``DatabaseResumingError`` until ``seconds`` have passed."""

    inner: QueryExecutor
    seconds: float
    clock: Callable[[], float] = time.monotonic
    _started: float | None = None

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        now = self.clock()
        if self._started is None:
            self._started = now
        if now - self._started < self.seconds:
            raise DatabaseResumingError("simulated resume (--simulate-resume)")
        return self.inner.execute(sql, max_rows=max_rows)


@dataclass(frozen=True)
class FixedSqlModel:
    """Answers every question with the same SQL, for UI work without Bedrock."""

    sql: str
    model_id: str = "fake (--fake-sql)"

    def complete(self, request: ModelRequest) -> ModelReply:
        text = reply_json(self.sql, interpretation="Offline answer from --fake-sql.")
        return ModelReply(text=text, model=self.model_id, input_tokens=0, output_tokens=0)


def make_handler(api: Api) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "olist-nlsql-local"

        def _dispatch(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            if length > api.settings.max_request_bytes:
                # don't read an oversized body; the API answers 413 from the length alone
                body = b"\0" * (api.settings.max_request_bytes + 1)
                self.close_connection = True
            else:
                body = self.rfile.read(length) if length else b""
            request = Request(
                method=self.command,
                path=self.path.split("?", 1)[0],
                headers={k.lower(): v for k, v in self.headers.items()},
                body=body,
            )
            self._send(api.handle(request))

        def _send(self, response: Response) -> None:
            payload = response.json()
            self.send_response(response.status)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _dispatch

        def log_message(self, format: str, *args: object) -> None:
            logger.info("%s %s", self.address_string(), format % args)

    return Handler


def serve(api: Api, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Create the server (bound, not yet serving). The caller runs ``serve_forever``."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("the local app binds to loopback only")
    return ThreadingHTTPServer((host, port), make_handler(api))
