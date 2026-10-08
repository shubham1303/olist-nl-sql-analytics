"""question -> model -> validator -> (maybe one repair) -> database

Rules this file sticks to (tests in tests/unit/test_pipeline.py):
- we only ever run the SQL the validator regenerates, never the model's text
- max two model calls per question
- the model never sees rows from the database
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from olist_nlsql.catalog import Catalog, load_catalog
from olist_nlsql.config import Settings
from olist_nlsql.db import ColumnInfo, QueryExecutionError, QueryExecutor, QueryTimeoutError
from olist_nlsql.llm.client import ModelClient, ModelError, ModelRequest
from olist_nlsql.llm.output import OUTPUT_SCHEMA, Generation, OutputParseError, parse_generation
from olist_nlsql.llm.prompts import (
    PROMPT_VERSION,
    REPAIRABLE,
    question_message,
    repair_message,
    system_prompt,
)
from olist_nlsql.sqlsafety import ErrorCode, SqlValidator, ValidationResult

logger = logging.getLogger(__name__)

Status = Literal[
    "answered",  # validated SQL executed
    "unanswerable",  # the model said the catalog cannot answer the question
    "invalid_question",  # rejected before any model call
    "generation_failed",  # model call failed or its reply could not be parsed
    "rejected",  # SQL still failed validation after the allowed repair
    "validator_error",  # the validator itself failed (a bug, not a user mistake)
    "execution_failed",  # the database rejected or timed out on validated SQL
]
Stage = Literal["input", "generation", "parsing", "validation", "validator_internal", "execution"]
AttemptKind = Literal["generation", "repair"]


@dataclass(frozen=True, slots=True)
class PipelineError:
    stage: Stage
    code: str  # validator ErrorCode, ModelError kind, or a pipeline code
    message: str  # shown to the user, so no tracebacks in here


@dataclass(frozen=True, slots=True)
class Attempt:
    """One model call and what happened to its SQL."""

    kind: AttemptKind
    model_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    sql: str | None = None  # SQL as the model wrote it (never executed)
    validation_ms: float | None = None
    validation_codes: tuple[str, ...] = ()  # empty when accepted or not validated
    outcome: Literal["accepted", "rejected", "unanswerable", "model_error", "parse_error"] = (
        "accepted"
    )


@dataclass(frozen=True, slots=True)
class Timings:
    prompt_build_ms: float
    model_generation_ms: float
    repair_generation_ms: float | None
    validation_ms: float
    execution_ms: float | None
    total_ms: float


@dataclass(frozen=True, slots=True)
class PipelineResult:
    question: str
    status: Status
    model_id: str
    prompt_version: str
    attempts: tuple[Attempt, ...]
    timings: Timings
    interpretation: str | None = None
    assumptions: tuple[str, ...] = ()
    metrics_used: tuple[str, ...] = ()
    validated_sql: str | None = None  # the SQL that was executed
    columns: tuple[ColumnInfo, ...] = ()
    rows: tuple[tuple[object, ...], ...] = ()
    truncated: bool = False
    warnings: tuple[str, ...] = ()
    error: PipelineError | None = None

    @property
    def generated_sql(self) -> str | None:
        return self.attempts[-1].sql if self.attempts else None

    @property
    def repair_attempted(self) -> bool:
        return any(a.kind == "repair" for a in self.attempts)

    @property
    def answer_source(self) -> AttemptKind | None:
        return self.attempts[-1].kind if self.status == "answered" else None

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 2)


@dataclass
class NlSqlPipeline:
    model: ModelClient
    validator: SqlValidator
    executor: QueryExecutor
    settings: Settings
    catalog: Catalog = field(default_factory=load_catalog)

    def ask(self, question: str) -> PipelineResult:
        run = _Run(self, question.strip())
        result = run.execute()
        _log(result)
        return result


class _Run:
    """Per-question state, pulled out so ask() stays short."""

    def __init__(self, pipeline: NlSqlPipeline, question: str) -> None:
        self.p = pipeline
        self.question = question
        self.start = time.perf_counter()
        self.attempts: list[Attempt] = []
        self.prompt_ms = 0.0
        self.validation_ms = 0.0
        self.execution_ms: float | None = None
        self.system = ""

    # flow

    def execute(self) -> PipelineResult:
        limit = self.p.settings.max_question_chars
        if not self.question:
            return self._fail(
                "invalid_question", "input", "EMPTY_QUESTION", "The question is empty."
            )
        if len(self.question) > limit:
            return self._fail(
                "invalid_question",
                "input",
                "QUESTION_TOO_LONG",
                f"The question is longer than {limit} characters.",
            )

        started = time.perf_counter()
        self.system = system_prompt(self.p.settings, self.p.catalog)
        first_message = question_message(self.question)
        self.prompt_ms = _ms(started)

        generation = self._generate("generation", first_message)
        if isinstance(generation, PipelineResult):
            return generation
        if not generation.can_answer:
            return self._finish("unanswerable", generation)

        validation = self._validate(generation.sql)
        if validation.internal_error:
            return self._validator_error(generation)
        if not validation.ok:
            issue = validation.errors[0]
            if issue.code not in REPAIRABLE:
                return self._rejected(generation, validation)
            repaired = self._generate(
                "repair", repair_message(self.question, generation.sql, issue, self.p.catalog)
            )
            if isinstance(repaired, PipelineResult):
                return repaired
            if not repaired.can_answer:
                return self._finish("unanswerable", repaired)
            generation, validation = repaired, self._validate(repaired.sql)
            if validation.internal_error:
                return self._validator_error(generation)
            if not validation.ok:
                return self._rejected(generation, validation)
        return self._run_sql(generation, validation)

    # stages

    def _generate(self, kind: AttemptKind, user: str) -> Generation | PipelineResult:
        request = ModelRequest(system=self.system, user=user, output_schema=OUTPUT_SCHEMA)
        started = time.perf_counter()
        try:
            reply = self.p.model.complete(request)
        except ModelError as exc:
            self.attempts.append(Attempt(kind, _ms(started), outcome="model_error"))
            return self._fail("generation_failed", "generation", exc.kind, str(exc))
        model_ms = _ms(started)
        try:
            generation = parse_generation(reply.text)
        except OutputParseError as exc:
            self.attempts.append(
                Attempt(
                    kind, model_ms, reply.input_tokens, reply.output_tokens, outcome="parse_error"
                )
            )
            return self._fail("generation_failed", "parsing", "OUTPUT_PARSE_ERROR", str(exc))
        self.attempts.append(
            Attempt(
                kind,
                model_ms,
                reply.input_tokens,
                reply.output_tokens,
                sql=generation.sql or None,
                outcome="accepted" if generation.can_answer else "unanswerable",
            )
        )
        return generation

    def _validate(self, sql: str) -> ValidationResult:
        started = time.perf_counter()
        result = self.p.validator.validate(sql)
        elapsed = _ms(started)
        self.validation_ms += elapsed
        last = self.attempts[-1]
        self.attempts[-1] = Attempt(
            last.kind,
            last.model_ms,
            last.input_tokens,
            last.output_tokens,
            sql=last.sql,
            validation_ms=elapsed,
            validation_codes=tuple(str(c) for c in result.codes),
            outcome="accepted" if result.ok else "rejected",
        )
        return result

    def _run_sql(self, generation: Generation, validation: ValidationResult) -> PipelineResult:
        if validation.sql is None:  # shouldn't happen, accepted results always have sql
            return self._validator_error(generation)
        started = time.perf_counter()
        try:
            data = self.p.executor.execute(validation.sql, max_rows=self.p.settings.max_result_rows)
        except QueryTimeoutError:
            self.execution_ms = _ms(started)
            return self._fail(
                "execution_failed",
                "execution",
                "QUERY_TIMEOUT",
                "The query exceeded the database time limit.",
                generation,
                validation,
            )
        except QueryExecutionError as exc:
            self.execution_ms = _ms(started)
            return self._fail(
                "execution_failed",
                "execution",
                "QUERY_FAILED",
                f"The database rejected the query: {str(exc).splitlines()[0][:200]}",
                generation,
                validation,
            )
        self.execution_ms = _ms(started)
        return self._result(
            "answered",
            generation,
            validation,
            columns=data.columns,
            rows=data.rows,
            truncated=data.truncated,
        )

    # endings

    def _rejected(self, generation: Generation, validation: ValidationResult) -> PipelineResult:
        issue = validation.errors[0]
        return self._fail("rejected", "validation", str(issue.code), issue.message, generation)

    def _validator_error(self, generation: Generation) -> PipelineResult:
        return self._fail(
            "validator_error",
            "validator_internal",
            str(ErrorCode.VALIDATOR_INTERNAL_ERROR),
            "An internal error in the SQL validator stopped this query. It is not a problem "
            "with the question.",
            generation,
        )

    def _finish(self, status: Status, generation: Generation) -> PipelineResult:
        return self._result(status, generation, None)

    def _fail(
        self,
        status: Status,
        stage: Stage,
        code: str,
        message: str,
        generation: Generation | None = None,
        validation: ValidationResult | None = None,
    ) -> PipelineResult:
        return self._result(
            status, generation, validation, error=PipelineError(stage, code, message)
        )

    def _result(
        self,
        status: Status,
        generation: Generation | None,
        validation: ValidationResult | None,
        *,
        columns: tuple[ColumnInfo, ...] = (),
        rows: tuple[tuple[object, ...], ...] = (),
        truncated: bool = False,
        error: PipelineError | None = None,
    ) -> PipelineResult:
        model_ms = [a.model_ms for a in self.attempts]
        timings = Timings(
            prompt_build_ms=self.prompt_ms,
            model_generation_ms=model_ms[0] if model_ms else 0.0,
            repair_generation_ms=model_ms[1] if len(model_ms) > 1 else None,
            validation_ms=round(self.validation_ms, 2),
            execution_ms=self.execution_ms,
            total_ms=_ms(self.start),
        )
        executed = (
            validation.sql
            if validation is not None and status in ("answered", "execution_failed")
            else None
        )
        return PipelineResult(
            question=self.question,
            status=status,
            model_id=self.p.model.model_id,
            prompt_version=PROMPT_VERSION,
            attempts=tuple(self.attempts),
            timings=timings,
            interpretation=generation.interpretation if generation else None,
            assumptions=generation.assumptions if generation else (),
            metrics_used=generation.metrics_used if generation else (),
            validated_sql=executed,
            columns=columns,
            rows=rows,
            truncated=truncated,
            warnings=tuple(w.message for w in validation.warnings) if validation else (),
            error=error,
        )


# output


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value
    isoformat: Callable[[], str] | None = getattr(value, "isoformat", None)
    if isoformat is not None:
        return isoformat()
    return str(value)  # Decimal and anything else: exact text


def to_dict(result: PipelineResult) -> dict[str, object]:
    """A JSON-safe view of a result (decimals as strings, dates as ISO text)."""
    return {
        "question": result.question,
        "status": result.status,
        "model_id": result.model_id,
        "prompt_version": result.prompt_version,
        "interpretation": result.interpretation,
        "assumptions": list(result.assumptions),
        "metrics_used": list(result.metrics_used),
        "generated_sql": result.generated_sql,
        "validated_sql": result.validated_sql,
        "repair_attempted": result.repair_attempted,
        "answer_source": result.answer_source,
        "columns": [{"name": c.name, "type": c.type} for c in result.columns],
        "rows": [[_jsonable(v) for v in row] for row in result.rows],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "warnings": list(result.warnings),
        "timings": {
            "prompt_build_ms": result.timings.prompt_build_ms,
            "model_generation_ms": result.timings.model_generation_ms,
            "repair_generation_ms": result.timings.repair_generation_ms,
            "validation_ms": result.timings.validation_ms,
            "execution_ms": result.timings.execution_ms,
            "total_ms": result.timings.total_ms,
        },
        "attempts": [
            {
                "kind": a.kind,
                "outcome": a.outcome,
                "validation_codes": list(a.validation_codes),
                "model_ms": a.model_ms,
                "validation_ms": a.validation_ms,
                "input_tokens": a.input_tokens,
                "output_tokens": a.output_tokens,
            }
            for a in result.attempts
        ],
        "error": (
            {
                "stage": result.error.stage,
                "code": result.error.code,
                "message": result.error.message,
            }
            if result.error
            else None
        ),
    }


def _log(result: PipelineResult) -> None:
    """One log line per question (no result rows)."""
    record = to_dict(result)
    record.pop("rows")
    record.pop("columns")
    level = logging.ERROR if result.status == "validator_error" else logging.INFO
    logger.log(level, json.dumps({"event": "nlsql_pipeline", **record}, default=str))
