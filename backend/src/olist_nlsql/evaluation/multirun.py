"""Compare repeated dev runs before and after a change (plan.md §6, small benchmark).

One run can move by a couple of items with nothing changed (four identical runs scored
30, 30, 30, 28), so a before/after claim uses at least MIN_RUNS runs per side and
reports the mean and minimum correct count:

- improvement: the mean rises and the minimum does not fall,
- regression: the mean falls and the maximum does not rise,
- otherwise no clear difference.

Every number is computed from the run records named in the report.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean

from olist_nlsql.evaluation.runner import RunRecord

MIN_RUNS = 3


@dataclass(frozen=True, slots=True)
class SideStats:
    runs: tuple[str, ...]
    correct: tuple[int, ...]
    scored: int

    @property
    def mean(self) -> float:
        return mean(self.correct)

    @property
    def min(self) -> int:
        return min(self.correct)

    @property
    def max(self) -> int:
        return max(self.correct)


def _correct_by_item(record: RunRecord) -> dict[str, bool]:
    return {i.id: bool(i.correct) for i in record.items if i.verified}


def side_stats(records: Sequence[RunRecord]) -> SideStats:
    scored = {len(_correct_by_item(r)) for r in records}
    if len(scored) != 1:
        raise ValueError("runs on one side scored different numbers of items")
    return SideStats(
        runs=tuple(r.run_id for r in records),
        correct=tuple(sum(_correct_by_item(r).values()) for r in records),
        scored=scored.pop(),
    )


def verdict(before: SideStats, after: SideStats) -> str:
    if min(len(before.correct), len(after.correct)) < MIN_RUNS:
        return f"not enough runs for a verdict (need {MIN_RUNS} per side)"
    if after.mean > before.mean and after.min >= before.min:
        return "improvement"
    if after.mean < before.mean and after.max <= before.max:
        return "regression"
    return "no clear difference"


def _check(before: Sequence[RunRecord], after: Sequence[RunRecord]) -> None:
    records = [*before, *after]
    if not before or not after:
        raise ValueError("need at least one run on each side")
    if {r.split for r in records} != {"dev"}:
        raise ValueError("compare is for dev runs; held-out runs are never used to judge a change")
    if any(r.fake_model for r in records):
        raise ValueError("fake-model runs are harness self-tests, not results")
    if len({r.benchmark_hash for r in records}) != 1:
        raise ValueError("runs use different benchmark versions; compare like with like")
    if len({frozenset(_correct_by_item(r)) for r in records}) != 1:
        raise ValueError("runs scored different items; compare full runs of the same split")
    for side, name in ((before, "before"), (after, "after")):
        if len({(r.model_id, r.prompt_version) for r in side}) != 1:
            raise ValueError(f"the {name} runs mix models or prompt versions")


def render(before: Sequence[RunRecord], after: Sequence[RunRecord]) -> str:
    _check(before, after)
    b, a = side_stats(before), side_stats(after)
    n = b.scored

    def describe(side: Sequence[RunRecord]) -> str:
        r = side[0]
        return f"`{r.model_id}`, prompt {r.prompt_version}, commit `{(r.git_commit or '?')[:7]}`"

    lines = [
        "# Dev comparison",
        "",
        f"**Verdict: {verdict(b, a)}** (improvement = mean up and minimum not down; "
        f"regression = mean down and maximum not up; {MIN_RUNS}+ runs per side)",
        "",
        "| | Runs | Correct per run | Mean | Min | Max |",
        "|---|---:|---|---:|---:|---:|",
        f"| Before ({describe(before)}) | {len(b.correct)} | {', '.join(map(str, b.correct))} "
        f"| {b.mean:.2f}/{n} | {b.min} | {b.max} |",
        f"| After ({describe(after)}) | {len(a.correct)} | {', '.join(map(str, a.correct))} "
        f"| {a.mean:.2f}/{n} | {a.min} | {a.max} |",
        "",
    ]
    per_before = [_correct_by_item(r) for r in before]
    per_after = [_correct_by_item(r) for r in after]
    unstable = [
        (item, sum(r[item] for r in per_before), sum(r[item] for r in per_after))
        for item in per_before[0]
        if not all(r[item] for r in (*per_before, *per_after))
    ]
    if unstable:
        lines += [
            "Items not correct in every run:",
            "",
            "| Item | Before correct | After correct |",
            "|---|---:|---:|",
            *[
                f"| {item} | {kb}/{len(per_before)} | {ka}/{len(per_after)} |"
                for item, kb, ka in unstable
            ],
            "",
        ]
    lines += ["Runs:", ""]
    lines += [f"- before: `{run}`" for run in b.runs]
    lines += [f"- after: `{run}`" for run in a.runs]
    return "\n".join(lines) + "\n"
