"""Benchmark files: strict loading, verification pinning, and the committed files."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from olist_nlsql.db import ColumnInfo
from olist_nlsql.evaluation import benchmark as bm
from olist_nlsql.evaluation.__main__ import check
from olist_nlsql.evaluation.compare import CompareOptions, Table

RESULT = Table((ColumnInfo("revenue", "number"),), ((Decimal("13494400.74"),),))


BASE = bm.BenchmarkItem(
    id="dev-001",
    question="What was total revenue?",
    difficulty="easy",
    tags=("aggregation",),
    reference_sql="SELECT SUM(revenue) AS revenue FROM orders",
    reference_result=RESULT,
)


def item(**changes: Any) -> bm.BenchmarkItem:
    return replace(BASE, **changes)


def test_verify_pins_the_content() -> None:
    verified = item().verify("Reviewer", date(2026, 10, 8))
    assert verified.verified
    edited = replace(verified, reference_sql="SELECT 1")
    assert not edited.verified and edited.verification_stale


def test_verify_needs_a_snapshot_and_a_name() -> None:
    with pytest.raises(bm.BenchmarkError, match="snapshot"):
        item(reference_result=None).verify("Reviewer", date(2026, 10, 8))
    with pytest.raises(bm.BenchmarkError, match="empty"):
        item().verify("  ", date(2026, 10, 8))


def test_unchanged_snapshot_keeps_verification_changed_one_clears_it() -> None:
    verified = item().verify("Reviewer", date(2026, 10, 8))
    assert verified.with_result(RESULT).verified
    changed = Table(RESULT.columns, ((Decimal("1.00"),),))
    cleared = verified.with_result(changed)
    assert not cleared.verified and cleared.verified_by is None


def test_dump_and_parse_round_trip_keeps_verification() -> None:
    original = bm.Benchmark(
        "dev",
        (
            item(compare=CompareOptions(order_matters=True, abs_tol=Decimal("0.01"))).verify(
                "Reviewer", date(2026, 10, 8)
            ),
            item(id="dev-002", question="Another?", reference_result=None, notes="a note"),
        ),
    )
    loaded = bm.parse(bm.dump(original), "dev")
    assert loaded.items == original.items
    assert loaded.items[0].verified
    assert loaded.verified_count == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"id": "test-001"}, "must start with 'dev-'"),
        ({"difficulty": "trivial"}, "difficulty"),
        ({"tags": ["unknown-tag"]}, "area"),
        ({"surprise": 1}, "unknown keys"),
    ],
)
def test_malformed_items_are_rejected(change: dict[str, object], message: str) -> None:
    raw = {
        "id": "dev-001",
        "question": "Q?",
        "difficulty": "easy",
        "tags": ["aggregation"],
        "reference_sql": "SELECT 1",
        **change,
    }
    text = yaml.safe_dump({"version": 1, "split": "dev", "items": [raw]})
    with pytest.raises(bm.BenchmarkError, match=message):
        bm.parse(text, "dev")


def test_duplicate_ids_are_rejected() -> None:
    text = bm.dump(bm.Benchmark("dev", (item(), item(question="Other?"))))
    with pytest.raises(bm.BenchmarkError, match="duplicate"):
        bm.parse(text, "dev")


def test_save_writes_where_load_reads(tmp_path: Path) -> None:
    bm.save(bm.Benchmark("dev", (item(),)), bm.benchmark_path("dev", tmp_path))
    assert bm.load("dev", tmp_path).items == (item(),)


# the committed benchmark


def test_committed_benchmark_loads_and_passes_check() -> None:
    benchmarks = bm.load_all()
    assert check(benchmarks) == []


def test_committed_benchmark_has_snapshots_and_covers_every_area() -> None:
    benchmarks = bm.load_all()
    items = [i for b in benchmarks.values() for i in b.items]
    assert all(i.reference_result is not None for i in items)
    assert not [i.id for i in items if i.verification_stale]
    for split, b in benchmarks.items():
        assert {d for i in b.items for d in [i.difficulty]} == set(bm.DIFFICULTIES), split
    assert {t for i in items for t in i.tags} >= set(bm.AREAS)


def test_committed_files_are_in_canonical_form() -> None:
    """snapshot/verify rewrite the files; a hand edit that changes formatting shows here."""
    for split, benchmark in bm.load_all().items():
        assert benchmark.path is not None
        assert benchmark.path.read_text(encoding="utf-8") == bm.dump(benchmark), split


def test_snapshot_from_the_database_hashes_like_its_stored_form() -> None:
    """A fresh result (date objects, floats) must not look changed against the same values
    read back from YAML (text dates, decimals); otherwise snapshot would report false
    changes and clear verifications."""
    fresh = Table(
        (ColumnInfo("month", "date"), ColumnInfo("median_days", "number")),
        ((date(2018, 1, 1), 10.22),),
    )
    stored = bm.parse(bm.dump(bm.Benchmark("dev", (item(reference_result=fresh),))), "dev")
    reread = stored.items[0]
    assert reread.reference_result != fresh  # different Python types...
    assert reread.content_hash() == item(reference_result=fresh).content_hash()  # same content
    verified = reread.verify("Reviewer", date(2026, 10, 9))
    assert verified.with_result(fresh).verified
