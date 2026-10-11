"""Benchmark files: eval/benchmark/{dev,test}.yaml (ADR 0006).

Each item carries its reference SQL, a stored snapshot of the reference result and
who verified it. Verification is pinned to a hash of the question, SQL, comparison
options and result: change any of them and the item counts as unverified again
until a person re-checks it. Unverified items are run but never scored.

The files are rewritten by ``snapshot`` and ``verify``, so comments in them are not
preserved; put explanations in an item's ``notes``.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml

from olist_nlsql.db import ColumnInfo, ResultType
from olist_nlsql.dbsetup.env import REPO_ROOT
from olist_nlsql.evaluation.compare import DEFAULT_ABS_TOL, DEFAULT_REL_TOL, CompareOptions, Table

Split = Literal["dev", "test"]
SPLITS: tuple[Split, ...] = ("dev", "test")
Difficulty = Literal["easy", "medium", "hard"]
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
EXPECTED_SIZES: dict[Split, int] = {"dev": 30, "test": 20}

# Areas from ADR 0006. Every item has at least one.
AREAS = (
    "filtering",
    "aggregation",
    "join",
    "time_series",
    "customer",
    "seller",
    "product_category",
    "delivery",
    "review",
    "multi_step",
)
RESULT_TYPES: tuple[str, ...] = get_args(ResultType)
FILE_VERSION = 1

BENCHMARK_DIR = REPO_ROOT / "eval" / "benchmark"


class BenchmarkError(ValueError):
    """A benchmark file is malformed."""


@dataclass(frozen=True, slots=True)
class BenchmarkItem:
    id: str
    question: str
    difficulty: Difficulty
    tags: tuple[str, ...]
    reference_sql: str
    compare: CompareOptions = field(default_factory=CompareOptions)
    reference_result: Table | None = None
    verified_by: str | None = None
    verified_on: date | None = None
    verified_hash: str | None = None
    notes: str | None = None

    def content_hash(self) -> str:
        """What a verification vouches for. Excludes notes, tags and difficulty."""
        payload = {
            "question": self.question,
            "reference_sql": self.reference_sql,
            "compare": _dump_compare(self.compare),
            "reference_result": _dump_result(self.reference_result),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    @property
    def verified(self) -> bool:
        return (
            self.reference_result is not None
            and bool(self.verified_by)
            and self.verified_on is not None
            and self.verified_hash == self.content_hash()
        )

    @property
    def verification_stale(self) -> bool:
        """Marked verified, but the item changed afterwards."""
        return bool(self.verified_by) and not self.verified

    def with_result(self, result: Table) -> "BenchmarkItem":
        """New snapshot. Verification survives only if the result is unchanged."""
        updated = replace(self, reference_result=result)
        if self.verified and updated.content_hash() != self.verified_hash:
            updated = replace(updated, verified_by=None, verified_on=None, verified_hash=None)
        return updated

    def verify(self, by: str, on: date) -> "BenchmarkItem":
        if self.reference_result is None:
            raise BenchmarkError(f"{self.id}: snapshot the reference result before verifying")
        if not by.strip():
            raise BenchmarkError("verified_by must not be empty")
        return replace(self, verified_by=by.strip(), verified_on=on, verified_hash=None).sealed()

    def sealed(self) -> "BenchmarkItem":
        return replace(self, verified_hash=self.content_hash())


@dataclass(frozen=True, slots=True)
class Benchmark:
    split: Split
    items: tuple[BenchmarkItem, ...]
    path: Path | None = None

    def item(self, item_id: str) -> BenchmarkItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise BenchmarkError(f"no item {item_id!r} in the {self.split} split")

    def replace_item(self, new: BenchmarkItem) -> "Benchmark":
        self.item(new.id)
        return replace(self, items=tuple(new if i.id == new.id else i for i in self.items))

    @property
    def verified_count(self) -> int:
        return sum(i.verified for i in self.items)

    def file_hash(self) -> str:
        return hashlib.sha256(dump(self).encode()).hexdigest()


# results <-> plain data. Numbers are stored as text so they survive YAML exactly.


def _dump_cell(value: object, kind: str) -> object:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and kind == "integer":
        return value
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _dump_result(result: Table | None) -> dict[str, Any] | None:
    if result is None:
        return None
    kinds = [c.type for c in result.columns]
    return {
        "columns": [{"name": c.name, "type": c.type} for c in result.columns],
        "rows": [
            [_dump_cell(v, k) for v, k in zip(row, kinds, strict=True)] for row in result.rows
        ],
    }


def _load_cell(value: object, kind: str, where: str) -> object:
    if value is None:
        return None
    if kind == "number":
        try:
            return Decimal(str(value))
        except InvalidOperation:
            raise BenchmarkError(f"{where}: {value!r} is not a number") from None
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise BenchmarkError(f"{where}: {value!r} is not an integer")
        return value
    if kind == "boolean":
        if not isinstance(value, bool):
            raise BenchmarkError(f"{where}: {value!r} is not a boolean")
        return value
    return str(value)


def _load_result(raw: object, where: str) -> Table | None:
    if raw is None:
        return None
    data = _mapping(raw, where, required={"columns", "rows"})
    columns = []
    for i, col in enumerate(_sequence(data["columns"], f"{where}.columns")):
        c = _mapping(col, f"{where}.columns[{i}]", required={"name", "type"})
        if c["type"] not in RESULT_TYPES:
            raise BenchmarkError(f"{where}.columns[{i}]: unknown type {c['type']!r}")
        columns.append(ColumnInfo(str(c["name"]), cast(ResultType, c["type"])))
    rows = []
    for r, row in enumerate(_sequence(data["rows"], f"{where}.rows")):
        cells = _sequence(row, f"{where}.rows[{r}]")
        if len(cells) != len(columns):
            raise BenchmarkError(f"{where}.rows[{r}]: expected {len(columns)} values")
        rows.append(
            tuple(
                _load_cell(v, c.type, f"{where}.rows[{r}]")
                for v, c in zip(cells, columns, strict=True)
            )
        )
    return Table(tuple(columns), tuple(rows))


def _dump_compare(options: CompareOptions) -> dict[str, Any]:
    return {
        "order_matters": options.order_matters,
        "abs_tol": str(options.abs_tol),
        "rel_tol": str(options.rel_tol),
        "allow_extra_columns": options.allow_extra_columns,
        "allow_percent": options.allow_percent,
    }


def _load_compare(raw: object, where: str) -> CompareOptions:
    if raw is None:
        return CompareOptions()
    data = _mapping(
        raw,
        where,
        optional={"order_matters", "abs_tol", "rel_tol", "allow_extra_columns", "allow_percent"},
    )
    try:
        return CompareOptions(
            order_matters=bool(data.get("order_matters", False)),
            abs_tol=Decimal(str(data.get("abs_tol", DEFAULT_ABS_TOL))),
            rel_tol=Decimal(str(data.get("rel_tol", DEFAULT_REL_TOL))),
            allow_extra_columns=bool(data.get("allow_extra_columns", True)),
            allow_percent=bool(data.get("allow_percent", False)),
        )
    except InvalidOperation:
        raise BenchmarkError(f"{where}: tolerances must be numbers") from None


# validation helpers


def _mapping(
    raw: object,
    where: str,
    *,
    required: set[str] | frozenset[str] = frozenset(),
    optional: set[str] | frozenset[str] = frozenset(),
) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise BenchmarkError(f"{where}: expected a mapping")
    missing = required - raw.keys()
    if missing:
        raise BenchmarkError(f"{where}: missing {', '.join(sorted(missing))}")
    unknown = raw.keys() - required - optional
    if unknown:
        raise BenchmarkError(f"{where}: unknown keys {', '.join(sorted(map(str, unknown)))}")
    return raw


def _sequence(raw: object, where: str) -> Sequence[Any]:
    if not isinstance(raw, list):
        raise BenchmarkError(f"{where}: expected a list")
    return raw


def _text(raw: object, where: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise BenchmarkError(f"{where}: expected non-empty text")
    return raw.strip()


_ITEM_REQUIRED = frozenset({"id", "question", "difficulty", "tags", "reference_sql"})
_ITEM_OPTIONAL = frozenset(
    {"compare", "reference_result", "verified_by", "verified_on", "verified_hash", "notes"}
)


def _load_item(raw: object, split: Split, index: int) -> BenchmarkItem:
    where = f"{split}.items[{index}]"
    data = _mapping(raw, where, required=_ITEM_REQUIRED, optional=_ITEM_OPTIONAL)
    item_id = _text(data["id"], f"{where}.id")
    where = f"{split}:{item_id}"
    if not item_id.startswith(f"{split}-"):
        raise BenchmarkError(f"{where}: id must start with '{split}-'")
    if data["difficulty"] not in DIFFICULTIES:
        raise BenchmarkError(f"{where}: difficulty must be one of {', '.join(DIFFICULTIES)}")
    tags = tuple(_text(t, f"{where}.tags") for t in _sequence(data["tags"], f"{where}.tags"))
    if not any(t in AREAS for t in tags):
        raise BenchmarkError(f"{where}: tags need at least one area ({', '.join(AREAS)})")
    verified_on = data.get("verified_on")
    if verified_on is not None and not isinstance(verified_on, date):
        try:
            verified_on = date.fromisoformat(str(verified_on))
        except ValueError:
            raise BenchmarkError(f"{where}.verified_on: expected YYYY-MM-DD") from None
    notes = data.get("notes")
    return BenchmarkItem(
        id=item_id,
        question=_text(data["question"], f"{where}.question"),
        difficulty=cast(Difficulty, data["difficulty"]),
        tags=tags,
        reference_sql=_text(data["reference_sql"], f"{where}.reference_sql"),
        compare=_load_compare(data.get("compare"), f"{where}.compare"),
        reference_result=_load_result(data.get("reference_result"), f"{where}.reference_result"),
        verified_by=data.get("verified_by") or None,
        verified_on=verified_on,
        verified_hash=data.get("verified_hash") or None,
        notes=notes.strip() if isinstance(notes, str) and notes.strip() else None,
    )


def parse(text: str, split: Split, path: Path | None = None) -> Benchmark:
    raw = yaml.safe_load(text)
    data = _mapping(raw, split, required={"version", "split", "items"})
    if data["version"] != FILE_VERSION:
        raise BenchmarkError(f"{split}: unsupported version {data['version']!r}")
    if data["split"] != split:
        raise BenchmarkError(f"{split}: file says split {data['split']!r}")
    items = tuple(
        _load_item(raw_item, split, i)
        for i, raw_item in enumerate(_sequence(data["items"], f"{split}.items"))
    )
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise BenchmarkError(f"{split}: duplicate id {item.id!r}")
        seen.add(item.id)
    return Benchmark(split, items, path)


def benchmark_path(split: Split, directory: Path = BENCHMARK_DIR) -> Path:
    return directory / f"{split}.yaml"


def load(split: Split, directory: Path = BENCHMARK_DIR) -> Benchmark:
    path = benchmark_path(split, directory)
    return parse(path.read_text(encoding="utf-8"), split, path)


def load_all(directory: Path = BENCHMARK_DIR) -> dict[Split, Benchmark]:
    benchmarks = {split: load(split, directory) for split in SPLITS}
    ids = [i.id for b in benchmarks.values() for i in b.items]
    questions = [i.question.casefold() for b in benchmarks.values() for i in b.items]
    if len(set(questions)) != len(questions):
        raise BenchmarkError("the same question appears more than once across splits")
    if len(set(ids)) != len(ids):
        raise BenchmarkError("duplicate ids across splits")
    return benchmarks


# writing


class _Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_presenter)


def _dump_item(item: BenchmarkItem) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": item.id,
        "question": item.question,
        "difficulty": item.difficulty,
        "tags": list(item.tags),
        "reference_sql": item.reference_sql.strip() + "\n",
    }
    if item.compare != CompareOptions():
        defaults = _dump_compare(CompareOptions())
        out["compare"] = {k: v for k, v in _dump_compare(item.compare).items() if defaults[k] != v}
    if item.notes:
        out["notes"] = item.notes
    out["reference_result"] = _dump_result(item.reference_result)
    out["verified_by"] = item.verified_by
    out["verified_on"] = item.verified_on.isoformat() if item.verified_on else None
    out["verified_hash"] = item.verified_hash
    return out


def dump(benchmark: Benchmark) -> str:
    data = {
        "version": FILE_VERSION,
        "split": benchmark.split,
        "items": [_dump_item(i) for i in benchmark.items],
    }
    header = (
        f"# {benchmark.split} split of the NL-to-SQL benchmark (ADR 0006).\n"
        "# Rewritten by `python -m olist_nlsql.evaluation snapshot|verify`; comments are lost.\n"
    )
    body = yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=None,
        width=100,
    )
    return header + body


def save(benchmark: Benchmark, path: Path | None = None) -> Path:
    target = path or benchmark.path or benchmark_path(benchmark.split)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump(benchmark), encoding="utf-8", newline="\n")
    return target
