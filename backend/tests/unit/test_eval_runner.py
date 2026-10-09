"""Runner, metrics and report with a fake model and a scripted executor (no db, no AWS)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from olist_nlsql.config import Settings
from olist_nlsql.db import ColumnInfo, QueryExecutionError, QueryResult
from olist_nlsql.evaluation import report, runner
from olist_nlsql.evaluation.benchmark import Benchmark, BenchmarkItem
from olist_nlsql.evaluation.compare import Table
from olist_nlsql.llm import ModelError
from olist_nlsql.llm.client import ModelClient
from olist_nlsql.llm.fake import FakeModelClient, reply_json

REVENUE = Table((ColumnInfo("revenue", "number"),), ((Decimal("13494400.74"),),))
SQL = "SELECT SUM(revenue) AS revenue FROM orders"


@dataclass
class ScriptedExecutor:
    """Returns the reference result for the reference SQL, a wrong number otherwise."""

    fail: bool = False

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        if self.fail:
            raise QueryExecutionError("boom")
        value = Decimal("13494400.74") if "revenue" in sql and "WHERE" not in sql else Decimal(1)
        return QueryResult((ColumnInfo("revenue", "number"),), ((value,),), truncated=False)


def make_item(item_id: str, *, verified: bool = True) -> BenchmarkItem:
    item = BenchmarkItem(
        item_id, f"Question {item_id}?", "easy", ("aggregation",), SQL, reference_result=REVENUE
    )
    return item.verify("Reviewer", date(2026, 10, 8)) if verified else item


def fixed_now() -> datetime:
    return datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def run_with(
    replies: dict[str, list[str | ModelError]],
    items: list[BenchmarkItem],
    executor: ScriptedExecutor | None = None,
    split: str = "dev",
    checkpoint: str | None = None,
) -> runner.RunRecord:
    def model_for(item: BenchmarkItem) -> ModelClient:
        return FakeModelClient(list(replies[item.id]), model_id="fake-model")

    return runner.run(
        Benchmark(split, tuple(items)),  # type: ignore[arg-type]
        model_for=model_for,
        executor=executor or ScriptedExecutor(),
        settings=Settings(),
        checkpoint=checkpoint,
        now=fixed_now,
    )


def test_outcomes_and_categories_per_pipeline_status() -> None:
    items = [make_item(f"dev-00{i}") for i in range(1, 6)]
    record = run_with(
        {
            "dev-001": [reply_json(SQL)],
            "dev-002": [
                reply_json("SELECT SUM(revenue) AS revenue FROM orders WHERE is_delivered")
            ],
            "dev-003": [ModelError("throttled", "slow down")],
            "dev-004": [reply_json("", can_answer=False)],
            # the validator rejects a hidden relation twice: initial try and repair
            "dev-005": [
                reply_json("SELECT SUM(total_revenue) FROM sellers"),
                reply_json("SELECT SUM(total_revenue) FROM sellers"),
            ],
        },
        items,
    )
    by_id = {o.id: o for o in record.items}
    assert by_id["dev-001"].correct and by_id["dev-001"].category == "correct"
    assert by_id["dev-002"].correct is False
    assert by_id["dev-002"].category == "untriaged_mismatch"
    assert by_id["dev-003"].category == "generation_failure"
    assert by_id["dev-003"].error_code == "throttled"
    assert by_id["dev-004"].category == "generation_failure" and not by_id["dev-004"].generated
    assert by_id["dev-005"].category == "validator_rejection"
    assert by_id["dev-005"].repair_attempted and by_id["dev-005"].model_calls == 2

    s = record.summary
    assert s["scored"] == 5
    assert s["counts"] == {"generated": 3, "validated": 2, "executed": 2, "correct": 1}
    assert s["rates"]["correct"] == 0.2
    assert s["repair_rate"] == 0.2


def test_execution_errors_are_categorised() -> None:
    record = run_with(
        {"dev-001": [reply_json(SQL)]}, [make_item("dev-001")], ScriptedExecutor(True)
    )
    assert record.items[0].category == "execution_error"
    assert record.summary["counts"]["validated"] == 1
    assert record.summary["counts"]["executed"] == 0


def test_unverified_items_run_but_are_not_scored() -> None:
    record = run_with(
        {"dev-001": [reply_json(SQL)], "dev-002": [reply_json(SQL)]},
        [make_item("dev-001"), make_item("dev-002", verified=False)],
    )
    assert record.summary["scored"] == 1 and record.summary["unverified"] == 1
    assert record.items[1].correct is True


def test_held_out_runs_need_a_checkpoint_reason() -> None:
    items = [make_item("test-001")]
    with pytest.raises(ValueError, match="checkpoint"):
        run_with({"test-001": [reply_json(SQL)]}, items, split="test")
    record = run_with({"test-001": [reply_json(SQL)]}, items, split="test", checkpoint="phase 4")
    assert record.checkpoint == "phase 4"


def test_reference_model_answers_with_reference_sql_and_is_marked_fake() -> None:
    record = runner.run(
        Benchmark("dev", (make_item("dev-001"),)),
        model_for=runner.reference_model,
        executor=ScriptedExecutor(),
        settings=Settings(),
        now=fixed_now,
    )
    assert record.fake_model and record.items[0].correct
    assert record.run_id == "20261008T120000Z_dev_fake-reference"
    assert "Harness self-test, not model accuracy" in report.render(record)


def test_record_round_trips_through_json(tmp_path: Path) -> None:
    record = run_with({"dev-001": [reply_json(SQL)]}, [make_item("dev-001")])
    path = runner.save(record, tmp_path)
    assert runner.from_json(path.read_text()) == record
    with pytest.raises(FileExistsError):
        runner.save(record, tmp_path)


def test_percentile_nearest_rank() -> None:
    assert runner.percentile([], 50) is None
    assert runner.percentile([5.0], 95) == 5.0
    assert runner.percentile([float(i) for i in range(1, 21)], 50) == 10.0
    assert runner.percentile([float(i) for i in range(1, 21)], 95) == 19.0


def test_triage_overrides_category_in_report(tmp_path: Path) -> None:
    record = run_with(
        {"dev-001": [reply_json("SELECT SUM(revenue) AS revenue FROM orders WHERE is_delivered")]},
        [make_item("dev-001")],
    )
    before = report.render(record)
    assert "untriaged_mismatch" in before and "still to triage: dev-001" in before
    path = tmp_path / "triage.yaml"
    path.write_text("dev-001:\n  category: wrong_filter_or_time_window\n  note: delivered only\n")
    triage = report.load_triage(path, record)
    after = report.render(record, triage)
    assert "wrong_filter_or_time_window (triaged)" in after
    assert "still to triage" not in after


def test_triage_rejects_unknown_items_and_categories(tmp_path: Path) -> None:
    record = run_with({"dev-001": [reply_json(SQL)]}, [make_item("dev-001")])
    path = tmp_path / "triage.yaml"
    path.write_text("dev-999:\n  category: ambiguity\n")
    with pytest.raises(report.TriageError, match="not in run"):
        report.load_triage(path, record)
    path.write_text("dev-001:\n  category: vibes\n")
    with pytest.raises(report.TriageError, match="category"):
        report.load_triage(path, record)


def test_held_out_report_shows_checkpoint() -> None:
    record = run_with(
        {"test-001": [reply_json(SQL)]}, [make_item("test-001")], split="test", checkpoint="why"
    )
    assert "Held-out checkpoint run.** Reason: why" in report.render(record)
