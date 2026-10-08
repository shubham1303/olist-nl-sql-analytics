"""Opt-in smoke test against real Bedrock: ``uv run pytest -m live -s``.

Runs five questions end to end to check auth, request format, parsing, validation
and execution. Not an accuracy test, that's Phase 4. Answers get printed so I can
copy them into docs/nl-to-sql.md; the asserts only cover the plumbing.

Skips cleanly when AWS credentials or Bedrock model access are unavailable.
"""

import json

import pytest

from olist_nlsql.config import load_settings
from olist_nlsql.db.postgres import PostgresExecutor
from olist_nlsql.dbsetup.env import load_dotenv, reader_conninfo
from olist_nlsql.llm.bedrock import BedrockModelClient
from olist_nlsql.llm.client import ModelError, ModelRequest
from olist_nlsql.llm.output import OUTPUT_SCHEMA
from olist_nlsql.pipeline import NlSqlPipeline, to_dict
from olist_nlsql.sqlsafety import SqlValidator

pytestmark = pytest.mark.live

QUESTIONS = [
    "What was total merchandise revenue in 2017?",
    "Which 5 product categories had the highest revenue?",
    "What is the late delivery rate?",
    "How many orders were placed each month in 2018?",
    "Which sellers with at least 20 delivered orders have the best average review score?",
]


@pytest.fixture(scope="module")
def pipeline() -> NlSqlPipeline:
    load_dotenv()
    settings = load_settings()
    model = BedrockModelClient(settings)
    try:  # one tiny call first, so a missing agreement skips instead of failing 5 times
        model.complete(ModelRequest("Reply with JSON.", "Say hi.", OUTPUT_SCHEMA))
    except ModelError as exc:
        if exc.kind in {"access_denied", "model_not_found", "connection"}:
            pytest.skip(f"Bedrock unavailable ({exc.kind}): {exc}")
        raise
    except Exception as exc:  # missing AWS credentials surface from botocore
        pytest.skip(f"AWS credentials unavailable: {type(exc).__name__}")
    executor = PostgresExecutor(reader_conninfo())
    return NlSqlPipeline(model, SqlValidator.from_catalog(settings=settings), executor, settings)


@pytest.mark.parametrize("question", QUESTIONS)
def test_question_runs_end_to_end(pipeline: NlSqlPipeline, question: str) -> None:
    result = pipeline.ask(question)
    record = to_dict(result)
    record["rows"] = record["rows"][:5]  # type: ignore[index]
    print("\nSMOKE", json.dumps(record, default=str))
    assert result.status in {"answered", "rejected", "unanswerable", "execution_failed"}
    assert len(result.attempts) <= 2
    if result.status == "answered":
        assert result.validated_sql is not None and result.columns
