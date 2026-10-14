"""AWS Lambda entry point behind the API Gateway HTTP API (payload format 2.0).

Translates the event into a ``Request`` for the shared ``Api`` and its ``Response``
back, and emits one EMF metrics line per request. The ``Api`` (catalog, validator,
Bedrock and Data API clients) is built once per container, on the first request, so
warm invocations only pay for the work.

Configuration comes from the function's environment (``NLSQL_*``, see config.py):
the access code hash, the cluster and analytics_reader secret ARNs, the model ID and
the limits. Terraform sets them.
"""

import base64
import logging
import time
from typing import Any

from olist_nlsql.api.handlers import Api, Request, Response
from olist_nlsql.api.metrics import emf_record, emit
from olist_nlsql.config import load_settings
from olist_nlsql.db.data_api import DataApiExecutor
from olist_nlsql.llm.bedrock import BedrockModelClient
from olist_nlsql.pipeline import NlSqlPipeline
from olist_nlsql.sqlsafety import SqlValidator

logger = logging.getLogger(__name__)
# Lambda's root logger is at WARNING; let the pipeline's one JSON line per question
# through. EMF metric lines go straight to stdout and don't depend on this.
logging.getLogger("olist_nlsql").setLevel(logging.INFO)

_api: Api | None = None


def build_api() -> Api:
    settings = load_settings()
    if not (settings.db_cluster_arn and settings.db_secret_arn):
        raise RuntimeError("NLSQL_DB_CLUSTER_ARN and NLSQL_DB_SECRET_ARN must be set")
    executor = DataApiExecutor(
        settings.db_cluster_arn,
        settings.db_secret_arn,
        settings.db_name,
        region=settings.aws_region,
    )
    pipeline = NlSqlPipeline(
        BedrockModelClient(settings),
        SqlValidator.from_catalog(settings=settings),
        executor,
        settings,
        probe_database=True,
    )
    return Api(settings, pipeline, executor)


def _api_instance() -> Api:
    global _api
    if _api is None:
        _api = build_api()
    return _api


def to_request(event: dict[str, Any]) -> Request:
    http = event.get("requestContext", {}).get("http", {})
    raw = event.get("body") or ""
    body = base64.b64decode(raw) if event.get("isBase64Encoded") else raw.encode("utf-8")
    return Request(
        method=str(http.get("method", "GET")),
        path=str(event.get("rawPath") or http.get("path") or "/"),
        headers={str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()},
        body=body,
    )


def to_event_response(response: Response) -> dict[str, Any]:
    return {
        "statusCode": response.status,
        "headers": response.headers,
        "body": response.json().decode("utf-8"),
        "isBase64Encoded": False,
    }


def handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = _api_instance().handle(to_request(event))
    except Exception:
        # Configuration or startup failure: fail closed with a generic message, details in logs.
        logger.exception("request failed before the API could answer")
        response = Response(
            500,
            {"error": {"code": "INTERNAL_ERROR", "message": "The service is not available."}},
            observation={"route": "other", "outcome": "INTERNAL_ERROR"},
        )
    emit(emf_record(response.observation, response.status, (time.perf_counter() - started) * 1000))
    return to_event_response(response)
