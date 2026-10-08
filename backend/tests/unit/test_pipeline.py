"""Pipeline behaviour with a fake model, the real validator and a recording executor.

No Bedrock, no database. Covers every flow and the security invariants that can be
checked without infrastructure.
"""

from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from olist_nlsql.config import Settings
from olist_nlsql.db import ColumnInfo, QueryExecutionError, QueryResult, QueryTimeoutError
from olist_nlsql.llm import ModelError
from olist_nlsql.llm.fake import FakeModelClient, reply_json
from olist_nlsql.llm.prompts import PROMPT_VERSION
from olist_nlsql.pipeline import NlSqlPipeline, PipelineResult, to_dict
from olist_nlsql.sqlsafety import ErrorCode, Issue, SqlValidator, ValidationResult

GOOD = "SELECT SUM(revenue) AS revenue FROM orders"
FANOUT = (
    "SELECT i.product_category, SUM(o.revenue) AS revenue FROM orders o "
    "JOIN order_items i ON o.order_id = i.order_id GROUP BY 1"
)
FIXED = (
    "SELECT product_category, SUM(revenue) AS revenue FROM order_items GROUP BY product_category"
)
STILL_BAD = "SELECT product_category, SUM(total_revenue) FROM products GROUP BY 1"


@dataclass
class RecordingExecutor:
    result: QueryResult = field(
        default_factory=lambda: QueryResult(
            columns=(ColumnInfo("revenue", "number"),),
            rows=((Decimal("13494400.74"),),),
            truncated=False,
        )
    )
    error: Exception | None = None
    executed: list[str] = field(default_factory=list)
    max_rows_seen: list[int] = field(default_factory=list)

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        self.executed.append(sql)
        self.max_rows_seen.append(max_rows)
        if self.error is not None:
            raise self.error
        return self.result


def run(
    *replies: str | ModelError,
    question: str = "What was total revenue?",
    executor: RecordingExecutor | None = None,
    validator: SqlValidator | None = None,
    settings: Settings | None = None,
) -> tuple[PipelineResult, FakeModelClient, RecordingExecutor]:
    model = FakeModelClient.of(*replies)
    executor = executor or RecordingExecutor()
    settings = settings or Settings()
    pipeline = NlSqlPipeline(
        model, validator or SqlValidator.from_catalog(settings=settings), executor, settings
    )
    return pipeline.ask(question), model, executor


# happy path


def test_first_pass_answer() -> None:
    result, model, _ = run(
        reply_json(GOOD, interpretation="Total merchandise revenue.", metrics_used=["revenue"])
    )
    assert result.status == "answered"
    assert result.answer_source == "generation" and not result.repair_attempted
    assert len(model.requests) == 1
    assert result.interpretation == "Total merchandise revenue."
    assert result.metrics_used == ("revenue",)
    assert result.columns == (ColumnInfo("revenue", "number"),)
    assert result.rows == ((Decimal("13494400.74"),),) and result.row_count == 1
    assert result.error is None


def test_assumptions_are_preserved() -> None:
    result, _, _ = run(
        reply_json(GOOD, assumptions=["Assuming 'sales' means merchandise revenue."])
    )
    assert result.assumptions == ("Assuming 'sales' means merchandise revenue.",)


def test_only_validator_output_is_executed_never_model_sql() -> None:
    result, _, executor = run(reply_json(GOOD))
    assert executor.executed == [result.validated_sql]
    assert result.generated_sql == GOOD
    assert result.validated_sql != GOOD  # regenerated: schema-qualified, limited
    assert "analytics.orders" in executor.executed[0] and "LIMIT 1001" in executor.executed[0]


def test_every_executed_query_passed_the_validator() -> None:
    validator = SqlValidator.from_catalog()
    result, _, executor = run(reply_json(FANOUT), reply_json(FIXED), validator=validator)
    assert result.status == "answered"
    for sql in executor.executed:
        assert validator.validate(sql).ok


def test_row_limit_is_passed_to_the_executor_and_truncation_reported() -> None:
    executor = RecordingExecutor(
        result=QueryResult(
            columns=(ColumnInfo("order_id", "text"),), rows=(("a",),) * 5, truncated=True
        )
    )
    result, _, _ = run(
        reply_json("SELECT order_id FROM orders"),
        executor=executor,
        settings=Settings(max_result_rows=5),
    )
    assert executor.max_rows_seen == [5]
    assert "LIMIT 6" in executor.executed[0]
    assert result.truncated and result.row_count == 5


def test_timings_and_metadata() -> None:
    result, _, _ = run(reply_json(GOOD))
    t = result.timings
    assert t.prompt_build_ms >= 0 and t.model_generation_ms >= 0 and t.validation_ms > 0
    assert t.execution_ms is not None and t.repair_generation_ms is None
    assert t.total_ms >= t.validation_ms
    assert result.prompt_version == PROMPT_VERSION and result.model_id == "fake-model"
    assert [a.outcome for a in result.attempts] == ["accepted"]


# repair


def test_one_repair_fixes_a_rejected_query() -> None:
    result, model, executor = run(reply_json(FANOUT), reply_json(FIXED, metrics_used=["revenue"]))
    assert result.status == "answered"
    assert result.repair_attempted and result.answer_source == "repair"
    assert len(model.requests) == 2 and len(executor.executed) == 1
    assert [a.kind for a in result.attempts] == ["generation", "repair"]
    assert result.attempts[0].validation_codes == ("FANOUT_RISK",)
    assert result.attempts[1].outcome == "accepted"
    assert result.generated_sql == FIXED
    assert result.timings.repair_generation_ms is not None


def test_repair_request_carries_the_question_rejected_sql_and_code() -> None:
    _, model, _ = run(reply_json(FANOUT), reply_json(FIXED), question="Revenue by category?")
    repair = model.requests[1]
    assert repair.system == model.requests[0].system  # same cached catalog prompt
    assert "Revenue by category?" in repair.user and FANOUT in repair.user
    assert "Error: FANOUT_RISK" in repair.user


def test_failed_repair_returns_a_structured_rejection_without_a_third_call() -> None:
    result, model, executor = run(reply_json(FANOUT), reply_json(STILL_BAD))
    assert result.status == "rejected"
    assert len(model.requests) == 2  # the fake would raise on a third call
    assert executor.executed == []
    assert result.error is not None and result.error.stage == "validation"
    assert result.error.code == "UNAPPROVED_COLUMN"
    assert result.validated_sql is None


def test_at_most_two_model_calls_even_if_every_answer_is_bad() -> None:
    bad = reply_json("SELECT * FROM orders")
    result, model, _ = run(bad, bad, bad, bad)
    assert len(model.requests) == 2
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "SELECT_STAR"


def test_write_attempts_are_not_repaired() -> None:
    result, model, executor = run(reply_json("DELETE FROM orders"), question="Delete all orders")
    assert result.status == "rejected" and len(model.requests) == 1
    assert result.error is not None and result.error.code == "WRITE_OPERATION"
    assert executor.executed == []


# failures


def test_model_exception_is_a_generation_failure() -> None:
    result, _, executor = run(ModelError("access_denied", "model not available for this account"))
    assert result.status == "generation_failed"
    assert result.error is not None and (result.error.stage, result.error.code) == (
        "generation",
        "access_denied",
    )
    assert executor.executed == [] and result.attempts[0].outcome == "model_error"


def test_model_exception_during_repair() -> None:
    result, _, executor = run(reply_json(FANOUT), ModelError("timeout", "timed out"))
    assert result.status == "generation_failed" and executor.executed == []
    assert [a.outcome for a in result.attempts] == ["rejected", "model_error"]


def test_malformed_output_is_a_generation_failure_without_repair() -> None:
    result, model, executor = run("SELECT SUM(revenue) FROM orders")  # raw SQL, not JSON
    assert result.status == "generation_failed" and len(model.requests) == 1
    assert result.error is not None and (result.error.stage, result.error.code) == (
        "parsing",
        "OUTPUT_PARSE_ERROR",
    )
    assert executor.executed == []


def test_unanswerable_question() -> None:
    result, _, executor = run(
        reply_json("", can_answer=False, interpretation="Product names are not in the data.")
    )
    assert result.status == "unanswerable" and executor.executed == []
    assert result.interpretation == "Product names are not in the data." and result.error is None


def test_validator_internal_error_is_distinguished_and_not_repaired() -> None:
    class BrokenValidator(SqlValidator):
        def validate(self, sql: str) -> ValidationResult:
            return ValidationResult(
                status="rejected",
                sql=None,
                errors=(
                    Issue(
                        ErrorCode.VALIDATOR_INTERNAL_ERROR, "internal", {"exception": "KeyError"}
                    ),
                ),
            )

    validator = BrokenValidator(SqlValidator.from_catalog().policy)
    result, model, executor = run(reply_json(GOOD), validator=validator)
    assert result.status == "validator_error" and len(model.requests) == 1
    assert result.error is not None and result.error.stage == "validator_internal"
    assert "not a problem with the question" in result.error.message
    assert "KeyError" not in result.error.message and "Traceback" not in result.error.message
    assert executor.executed == []


@pytest.mark.parametrize(
    ("error", "code"),
    [(QueryTimeoutError("canceling statement due to statement timeout"), "QUERY_TIMEOUT"),
     (QueryExecutionError("division by zero"), "QUERY_FAILED")],
)  # fmt: skip
def test_database_failures_are_execution_failures_without_repair(
    error: Exception, code: str
) -> None:
    result, model, executor = run(reply_json(GOOD), executor=RecordingExecutor(error=error))
    assert result.status == "execution_failed" and len(model.requests) == 1
    assert result.error is not None and (result.error.stage, result.error.code) == (
        "execution",
        code,
    )
    assert len(executor.executed) == 1 and result.validated_sql == executor.executed[0]


@pytest.mark.parametrize(
    ("question", "code"), [("   ", "EMPTY_QUESTION"), ("x" * 501, "QUESTION_TOO_LONG")]
)
def test_invalid_questions_never_reach_the_model(question: str, code: str) -> None:
    result, model, _ = run(question=question)
    assert result.status == "invalid_question" and model.requests == []
    assert result.error is not None and result.error.code == code


# invariants


def test_model_never_receives_database_rows() -> None:
    rows_marker = "UNIQUE-ROW-VALUE-7f3a"
    executor = RecordingExecutor(
        result=QueryResult(
            columns=(ColumnInfo("x", "text"),), rows=((rows_marker,),), truncated=False
        )
    )
    result, model, _ = run(reply_json(FANOUT), reply_json(FIXED), executor=executor)
    assert result.rows == ((rows_marker,),)
    assert all(rows_marker not in text for text in model.sent_text())
    assert len(model.requests) == 2  # no summarisation call after execution


def test_prompt_sent_to_the_model_excludes_hidden_relations() -> None:
    _, model, _ = run(reply_json(GOOD))
    system = model.requests[0].system
    assert "### customers" not in system and "### sellers" not in system
    assert "total_revenue" not in system


def test_result_serialises_to_json_safe_types() -> None:
    import json

    result, _, _ = run(reply_json(GOOD, metrics_used=["revenue"]))
    data = to_dict(result)
    assert json.loads(json.dumps(data))["rows"] == [["13494400.74"]]
    assert data["answer_source"] == "generation" and data["prompt_version"] == PROMPT_VERSION
