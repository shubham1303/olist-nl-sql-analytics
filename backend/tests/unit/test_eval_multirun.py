"""Before/after comparison of repeated dev runs (no db, no AWS)."""

from dataclasses import replace

import pytest

from olist_nlsql.evaluation import multirun, runner
from olist_nlsql.llm.fake import reply_json
from tests.unit.test_eval_runner import SQL, make_item, run_with

WRONG = "SELECT SUM(revenue) AS revenue FROM orders WHERE is_delivered"
IDS = ("dev-001", "dev-002", "dev-003")


def a_run(
    correct: int, prompt: str = "v1", changes: dict[str, object] | None = None
) -> runner.RunRecord:
    """A dev run over three items with the first ``correct`` items right."""
    replies = {i: [reply_json(SQL if n < correct else WRONG)] for n, i in enumerate(IDS)}
    record = run_with(replies, [make_item(i) for i in IDS])  # type: ignore[arg-type]
    fields: dict[str, object] = {"fake_model": False, "prompt_version": prompt, **(changes or {})}
    return replace(record, **fields)  # type: ignore[arg-type]


def stats(*correct: int) -> multirun.SideStats:
    return multirun.SideStats(tuple(f"r{i}" for i in range(len(correct))), correct, 3)


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ((2, 2, 2), (3, 3, 2), "improvement"),
        ((2, 2, 2), (3, 3, 1), "no clear difference"),  # mean up, but the minimum fell
        ((3, 3, 2), (2, 2, 2), "regression"),
        ((2, 2, 2), (2, 2, 2), "no clear difference"),
        ((2, 2), (3, 3, 3), "not enough runs for a verdict (need 3 per side)"),
    ],
)
def test_verdict_uses_mean_and_minimum(
    before: tuple[int, ...], after: tuple[int, ...], expected: str
) -> None:
    assert multirun.verdict(stats(*before), stats(*after)) == expected


def test_report_shows_runs_stats_and_unstable_items() -> None:
    md = multirun.render(
        [a_run(2), a_run(2), a_run(2)], [a_run(3, "v2"), a_run(3, "v2"), a_run(2, "v2")]
    )
    assert "**Verdict: improvement**" in md
    assert "| 3 | 2, 2, 2 | 2.00/3 | 2 | 2 |" in md
    assert "| 3 | 3, 3, 2 | 2.67/3 | 2 | 3 |" in md
    assert "| dev-003 | 0/3 | 2/3 |" in md
    assert "dev-001 |" not in md  # correct in every run


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"split": "test"}, "dev runs"),
        ({"fake_model": True}, "self-tests"),
        ({"benchmark_hash": "other"}, "benchmark versions"),
        ({"model_id": "other-model"}, "mix models"),
    ],
)
def test_comparisons_that_would_mislead_are_refused(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        multirun.render([a_run(2), a_run(2, changes=changes)], [a_run(3, "v2")])


def test_runs_over_different_items_are_refused() -> None:
    partial = a_run(2)
    partial = replace(partial, items=partial.items[:2])
    with pytest.raises(ValueError, match="different items"):
        multirun.render([a_run(2)], [partial])
