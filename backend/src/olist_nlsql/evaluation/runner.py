"""Run a benchmark split through the real pipeline and record what happened (ADR 0006).

One run = one JSON record in eval/results/, holding every item's outcome plus the run
metadata (git commit, model config, prompt version, benchmark hash). Metrics are
recomputed from the items, never typed in, so a report can always be traced back to
the record that produced it.

Held-out (test) runs need a checkpoint reason and are recorded like any other run, so
the number of held-out runs is visible from the results directory.
"""

import json
import re
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args

from olist_nlsql.config import Settings
from olist_nlsql.db import QueryExecutor
from olist_nlsql.dbsetup.env import REPO_ROOT
from olist_nlsql.evaluation.benchmark import Benchmark, BenchmarkItem
from olist_nlsql.evaluation.compare import Table, compare
from olist_nlsql.llm.client import ModelClient, ModelError
from olist_nlsql.llm.fake import FakeModelClient, reply_json
from olist_nlsql.llm.prompts import PROMPT_VERSION
from olist_nlsql.pipeline import NlSqlPipeline, PipelineResult
from olist_nlsql.sqlsafety import SqlValidator

RESULTS_DIR = REPO_ROOT / "eval" / "results"
RECORD_VERSION = 1
FAKE_REFERENCE_MODEL = "fake-reference"

# ADR 0006 failure categories. The first group is assigned automatically from the
# pipeline status; result mismatches get a best guess that a person confirms in a
# triage file (see report.py).
Category = Literal[
    "correct",
    "generation_failure",
    "validator_rejection",  # not yet split into correct / false rejection
    "validator_rejection_correct",
    "validator_rejection_false",
    "execution_error",
    "wrong_relation_or_join",
    "wrong_aggregation",
    "wrong_filter_or_time_window",
    "wrong_metric_definition",
    "ambiguity",
    "reference_error",
    "untriaged_mismatch",
    "no_reference",
]
CATEGORIES: tuple[str, ...] = get_args(Category)


@dataclass(frozen=True, slots=True)
class ItemOutcome:
    id: str
    question: str
    difficulty: str
    tags: tuple[str, ...]
    verified: bool
    status: str  # pipeline status
    generated: bool  # the model returned parseable SQL
    validated: bool  # the SQL passed the validator
    executed: bool  # the validated SQL ran
    correct: bool | None  # None when there is no reference result to compare with
    category: Category
    category_note: str
    error_code: str | None
    repair_attempted: bool
    answer_source: str | None
    model_calls: int
    input_tokens: int  # all input, cached or not
    cache_read_tokens: int
    output_tokens: int
    total_ms: float
    model_ms: float
    row_count: int
    truncated: bool
    interpretation: str | None
    assumptions: tuple[str, ...]
    generated_sql: str | None
    validated_sql: str | None
    reference_sql: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    split: str
    started_at: str
    finished_at: str
    git_commit: str | None
    git_dirty: bool | None
    model_id: str
    model_settings: dict[str, Any]
    prompt_version: str
    benchmark_hash: str
    checkpoint: str | None
    fake_model: bool
    items: tuple[ItemOutcome, ...]
    version: int = RECORD_VERSION
    summary: dict[str, Any] = field(default_factory=dict)


# categories


def _relations(validator: SqlValidator, sql: str | None) -> frozenset[str]:
    if not sql:
        return frozenset()
    result = validator.validate(sql)
    return frozenset(result.relations) if result.ok else frozenset()


def categorise(
    result: PipelineResult,
    item: BenchmarkItem,
    correct: bool | None,
    reason: str,
    validator: SqlValidator,
) -> tuple[Category, str]:
    """Automatic category plus a short note. Mismatches only get a best guess."""
    if result.status in ("generation_failed", "invalid_question"):
        code = result.error.code if result.error else "unknown"
        return "generation_failure", code
    if result.status == "unanswerable":
        return "generation_failure", "model said the question cannot be answered"
    if result.status in ("rejected", "validator_error"):
        code = result.error.code if result.error else "unknown"
        return "validator_rejection", code
    if result.status == "execution_failed":
        return "execution_error", result.error.code if result.error else "unknown"
    if correct is None:
        return "no_reference", "no reference result snapshot"
    if correct:
        return "correct", ""
    generated = _relations(validator, result.validated_sql)
    reference = _relations(validator, item.reference_sql)
    if generated and reference and generated != reference:
        used = ", ".join(sorted(generated))
        expected = ", ".join(sorted(reference))
        return "wrong_relation_or_join", f"used {used}; reference uses {expected}; {reason}"
    return "untriaged_mismatch", reason


# running


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 - fixed git arguments, no user input
            ["git", *args],  # noqa: S607 - git from PATH is intended
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def git_state() -> tuple[str | None, bool | None]:
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return commit, (None if status is None else bool(status))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def evaluate_item(
    item: BenchmarkItem, pipeline: NlSqlPipeline, validator: SqlValidator
) -> ItemOutcome:
    result = pipeline.ask(item.question)
    correct: bool | None = None
    reason = ""
    if result.status == "answered" and item.reference_result is not None:
        comparison = compare(
            item.reference_result, Table(result.columns, result.rows), item.compare
        )
        correct, reason = comparison.match, comparison.reason
    elif result.status != "answered" and item.reference_result is not None:
        correct = False
    category, note = categorise(result, item, correct, reason, validator)
    generated = any(a.sql for a in result.attempts) and result.status not in (
        "generation_failed",
        "unanswerable",
        "invalid_question",
    )
    validated = result.status in ("answered", "execution_failed")
    return ItemOutcome(
        id=item.id,
        question=item.question,
        difficulty=item.difficulty,
        tags=item.tags,
        verified=item.verified,
        status=result.status,
        generated=generated,
        validated=validated,
        executed=result.status == "answered",
        correct=correct,
        category=category,
        category_note=note,
        error_code=result.error.code if result.error else None,
        repair_attempted=result.repair_attempted,
        answer_source=result.answer_source,
        model_calls=len(result.attempts),
        input_tokens=sum(
            a.input_tokens + a.cache_read_tokens + a.cache_write_tokens for a in result.attempts
        ),
        cache_read_tokens=sum(a.cache_read_tokens for a in result.attempts),
        output_tokens=sum(a.output_tokens for a in result.attempts),
        total_ms=result.timings.total_ms,
        model_ms=round(sum(a.model_ms for a in result.attempts), 2),
        row_count=result.row_count,
        truncated=result.truncated,
        interpretation=result.interpretation,
        assumptions=result.assumptions,
        generated_sql=result.generated_sql,
        validated_sql=result.validated_sql,
        reference_sql=item.reference_sql,
    )


def reference_model(item: BenchmarkItem) -> ModelClient:
    """A fake model that answers with the item's own reference SQL.

    Used to test the harness end to end (it should score 100%). Its results are
    marked fake and must never be reported as model accuracy.
    """
    return FakeModelClient(
        [
            reply_json(item.reference_sql, interpretation="Reference SQL (harness self-test)."),
            ModelError("empty", "the reference model does not repair"),
        ],
        model_id=FAKE_REFERENCE_MODEL,
    )


def run(
    benchmark: Benchmark,
    *,
    model_for: Callable[[BenchmarkItem], ModelClient],
    executor: QueryExecutor,
    settings: Settings,
    checkpoint: str | None = None,
    ids: Sequence[str] = (),
    progress: Callable[[ItemOutcome], None] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RunRecord:
    if benchmark.split == "test" and not (checkpoint and checkpoint.strip()):
        raise ValueError("held-out (test) runs need a checkpoint reason (ADR 0006)")
    items = [benchmark.item(i) for i in ids] if ids else list(benchmark.items)
    validator = SqlValidator.from_catalog(settings=settings)
    started = now()
    outcomes = []
    model_ids: set[str] = set()
    for item in items:
        model = model_for(item)
        model_ids.add(model.model_id)
        pipeline = NlSqlPipeline(model, validator, executor, settings)
        outcome = evaluate_item(item, pipeline, validator)
        outcomes.append(outcome)
        if progress:
            progress(outcome)
    finished = now()
    model_id = ", ".join(sorted(model_ids)) or "none"
    fake = all(m.startswith("fake") for m in model_ids)
    commit, dirty = git_state()
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    record = RunRecord(
        run_id=f"{stamp}_{benchmark.split}_{_slug(model_id)}",
        split=benchmark.split,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=finished.isoformat(timespec="seconds"),
        git_commit=commit,
        git_dirty=dirty,
        model_id=model_id,
        model_settings={
            "region": settings.aws_region,
            "effort": settings.llm_effort,
            "thinking": settings.llm_thinking,
            "max_output_tokens": settings.llm_max_output_tokens,
            "timeout_seconds": settings.llm_timeout_seconds,
        },
        prompt_version=PROMPT_VERSION,
        benchmark_hash=benchmark.file_hash(),
        checkpoint=checkpoint.strip() if checkpoint else None,
        fake_model=fake,
        items=tuple(outcomes),
    )
    return _with_summary(record)


# metrics


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Nearest-rank percentile; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * pct // 100))  # ceil without floats drifting
    return ordered[int(rank) - 1]


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def summarise(
    items: Iterable[ItemOutcome], categories: dict[str, str] | None = None
) -> dict[str, Any]:
    """Stage metrics over verified items only (ADR 0006). ``categories`` overrides
    item categories (from a triage file)."""
    items = list(items)
    categories = categories or {}
    scored = [i for i in items if i.verified]
    n = len(scored)
    counts = {
        "generated": sum(i.generated for i in scored),
        "validated": sum(i.validated for i in scored),
        "executed": sum(i.executed for i in scored),
        "correct": sum(bool(i.correct) for i in scored),
    }
    repaired = [i for i in scored if i.repair_attempted]
    latency = [i.total_ms for i in scored]
    tokens = [i.input_tokens + i.output_tokens for i in scored]
    input_total = sum(i.input_tokens for i in scored)
    return {
        "items": len(items),
        "scored": n,
        "unverified": len(items) - n,
        "counts": counts,
        "rates": {k: _rate(v, n) for k, v in counts.items()},
        "repair_rate": _rate(len(repaired), n),
        "repair_success": _rate(sum(bool(i.correct) for i in repaired), len(repaired)),
        "latency_ms": {"p50": percentile(latency, 50), "p95": percentile(latency, 95)},
        "tokens_per_question": round(sum(tokens) / n, 1) if n else None,
        "output_tokens_per_question": round(sum(i.output_tokens for i in scored) / n, 1)
        if n
        else None,
        "cache_read_share": _rate(sum(i.cache_read_tokens for i in scored), input_total),
        "model_calls_per_question": round(sum(i.model_calls for i in scored) / n, 2) if n else None,
        "categories": dict(
            sorted(Counter(categories.get(i.id, i.category) for i in scored).items())
        ),
        "by_difficulty": {
            d: {
                "scored": sum(i.difficulty == d for i in scored),
                "correct": sum(i.difficulty == d and bool(i.correct) for i in scored),
            }
            for d in ("easy", "medium", "hard")
        },
    }


def _with_summary(record: RunRecord) -> RunRecord:
    return replace(record, summary=summarise(record.items))


# storage


def to_json(record: RunRecord) -> str:
    return json.dumps(asdict(record), indent=2, ensure_ascii=False) + "\n"


def from_json(text: str) -> RunRecord:
    data = json.loads(text)
    if data.get("version") != RECORD_VERSION:
        raise ValueError(f"unsupported run record version {data.get('version')!r}")
    data["items"] = tuple(
        ItemOutcome(**{**i, "tags": tuple(i["tags"]), "assumptions": tuple(i["assumptions"])})
        for i in data["items"]
    )
    return RunRecord(**data)


def save(record: RunRecord, directory: Path = RESULTS_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.run_id}.json"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.write_text(to_json(record), encoding="utf-8", newline="\n")
    return path
