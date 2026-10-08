"""Markdown report for a run record, with optional human triage (ADR 0006).

The harness can only guess why a result was wrong. A triage file records the
person's call per item and overrides the automatic category in the report:

    # eval/triage/<run_id>.yaml
    dev-007:
      category: wrong_filter_or_time_window
      note: used delivered orders only

Every number in the report is computed from the run record it names.
"""

from collections.abc import Mapping
from pathlib import Path

import yaml

from olist_nlsql.dbsetup.env import REPO_ROOT
from olist_nlsql.evaluation.runner import CATEGORIES, ItemOutcome, RunRecord, summarise

TRIAGE_DIR = REPO_ROOT / "eval" / "triage"


class TriageError(ValueError):
    pass


def load_triage(path: Path, record: RunRecord) -> dict[str, tuple[str, str]]:
    """item id -> (category, note)."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, Mapping):
        raise TriageError(f"{path}: expected a mapping of item id to category")
    known = {i.id for i in record.items}
    triage: dict[str, tuple[str, str]] = {}
    for item_id, entry in raw.items():
        if item_id not in known:
            raise TriageError(f"{path}: {item_id!r} is not in run {record.run_id}")
        if not isinstance(entry, Mapping) or entry.get("category") not in CATEGORIES:
            raise TriageError(f"{path}: {item_id}: category must be one of {', '.join(CATEGORIES)}")
        triage[str(item_id)] = (str(entry["category"]), str(entry.get("note") or ""))
    return triage


def triage_path(record: RunRecord, directory: Path = TRIAGE_DIR) -> Path:
    return directory / f"{record.run_id}.yaml"


def _pct(rate: object) -> str:
    return "n/a" if rate is None else f"{float(str(rate)) * 100:.1f}%"


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _item_row(item: ItemOutcome, triage: Mapping[str, tuple[str, str]]) -> str:
    category, note = triage.get(item.id, (item.category, item.category_note))
    source = "" if item.id not in triage else " (triaged)"
    correct = {True: "yes", False: "no", None: "-"}[item.correct]
    repair = "yes" if item.repair_attempted else ""
    return (
        f"| {item.id} | {item.difficulty} | {item.status} | {correct} | {repair} "
        f"| {category}{source} | {_cell(note)[:120]} | {item.total_ms:.0f} |"
    )


def render(record: RunRecord, triage: Mapping[str, tuple[str, str]] | None = None) -> str:
    triage = triage or {}
    summary = summarise(record.items, {k: v[0] for k, v in triage.items()})
    lines = [f"# Eval run `{record.run_id}`", ""]
    if record.fake_model:
        lines += [
            "> **Harness self-test, not model accuracy.** This run used a fake model "
            f"(`{record.model_id}`). Do not quote these numbers as results.",
            "",
        ]
    if record.split == "test":
        lines += [f"> **Held-out checkpoint run.** Reason: {record.checkpoint}", ""]
    dirty = {True: " (uncommitted changes)", False: "", None: " (unknown)"}[record.git_dirty]
    s = summary["counts"]
    rates = summary["rates"]
    n = summary["scored"]
    lines += [
        "| | |",
        "|---|---|",
        f"| Split | {record.split} |",
        f"| Started | {record.started_at} |",
        f"| Git commit | `{record.git_commit or 'unknown'}`{dirty} |",
        f"| Model | `{record.model_id}` |",
        f"| Model settings | {', '.join(f'{k}={v}' for k, v in record.model_settings.items())} |",
        f"| Prompt version | {record.prompt_version} |",
        f"| Benchmark hash | `{record.benchmark_hash[:16]}` |",
        f"| Items | {summary['items']} ({n} verified and scored, {summary['unverified']} "
        "unverified and not scored) |",
        "",
        "## Stage metrics (verified items)",
        "",
        "| Stage | Count | Rate |",
        "|---|---:|---:|",
        f"| SQL generated | {s['generated']}/{n} | {_pct(summary['rates']['generated'])} |",
        f"| Passed validation | {s['validated']}/{n} | {_pct(summary['rates']['validated'])} |",
        f"| Executed | {s['executed']}/{n} | {_pct(summary['rates']['executed'])} |",
        f"| **Correct result** | **{s['correct']}/{n}** | **{_pct(rates['correct'])}** |",
        "",
        "## Supporting metrics",
        "",
        f"- Repair rate: {_pct(summary['repair_rate'])}; repairs that ended correct: "
        f"{_pct(summary['repair_success'])}",
        f"- Latency p50 / p95: {summary['latency_ms']['p50']} / {summary['latency_ms']['p95']} ms",
        f"- Tokens per question: {summary['tokens_per_question']}; model calls per question: "
        f"{summary['model_calls_per_question']}",
        "",
        "| Difficulty | Correct |",
        "|---|---:|",
    ]
    for difficulty, d in summary["by_difficulty"].items():
        lines.append(f"| {difficulty} | {d['correct']}/{d['scored']} |")
    lines += [
        "",
        "## Failure categories (verified items)",
        "",
        "| Category | Items |",
        "|---|---:|",
    ]
    for category, count in summary["categories"].items():
        lines.append(f"| {category} | {count} |")
    untriaged = [
        i.id
        for i in record.items
        if i.verified
        and i.id not in triage
        and i.category in ("untriaged_mismatch", "validator_rejection", "wrong_relation_or_join")
    ]
    if untriaged:
        lines += [
            "",
            f"Automatic guesses still to triage: {', '.join(untriaged)} "
            f"(`eval/triage/{record.run_id}.yaml`).",
        ]
    header = "| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |"
    rule = "|---|---|---|---|---|---|---|---:|"
    lines += ["", "## Items", "", header, rule]
    lines += [_item_row(i, triage) for i in record.items if i.verified]
    unverified = [i for i in record.items if not i.verified]
    if unverified:
        lines += [
            "",
            "## Unverified items (run, not scored)",
            "",
            header,
            rule,
            *[_item_row(i, triage) for i in unverified],
        ]
    return "\n".join(lines) + "\n"
