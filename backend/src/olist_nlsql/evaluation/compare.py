"""Result comparison for the benchmark (ADR 0006).

A generated result matches the reference when:
- it has the same number of rows,
- every reference column can be paired with a different generated column holding
  the same values (column names are ignored, so is column order),
- the rows agree under that pairing, in order when ``order_matters`` and as a
  multiset otherwise,
- numbers agree within ``abs_tol`` or ``rel_tol``, whichever is looser.

Extra generated columns are allowed by default (a model that adds an order count
next to the revenue it was asked for still answered the question). A few harmless
formatting differences are normalised: integer vs numeric, a timestamp at midnight
vs a date, and a 'YYYY-MM' month label vs the first day of that month.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from olist_nlsql.db import ColumnInfo

DEFAULT_ABS_TOL = Decimal("0.005")  # half a centavo: allows rounding to 2 decimals
DEFAULT_REL_TOL = Decimal("0.000001")

_MONTH_LABEL = re.compile(r"^\d{4}-\d{2}$")
_MIDNIGHT = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]00:00:00$")

# A normalised cell: (kind, value). Kinds sort null < bool < number < text.
Cell = tuple[int, object]
_NULL, _BOOL, _NUM, _TEXT = 0, 1, 2, 3


@dataclass(frozen=True, slots=True)
class CompareOptions:
    order_matters: bool = False
    abs_tol: Decimal = DEFAULT_ABS_TOL
    rel_tol: Decimal = DEFAULT_REL_TOL
    allow_extra_columns: bool = True
    # rates: also accept a generated column that is the reference value x 100
    allow_percent: bool = False


@dataclass(frozen=True, slots=True)
class Table:
    columns: tuple[ColumnInfo, ...]
    rows: tuple[tuple[object, ...], ...]


@dataclass(frozen=True, slots=True)
class Comparison:
    match: bool
    reason: str  # why it failed, or "match"
    # generated column index for each reference column, when matched
    column_map: tuple[int, ...] | None = None
    extra_columns: int = 0


def normalise(value: object) -> Cell:
    if value is None:
        return (_NULL, None)
    if isinstance(value, bool):
        return (_BOOL, value)
    if isinstance(value, int):
        return (_NUM, Decimal(value))
    if isinstance(value, float):
        return (_NUM, Decimal(repr(value)))
    if isinstance(value, Decimal):
        return (_NUM, value)
    if isinstance(value, datetime):
        if value.time() == datetime.min.time():
            return (_TEXT, value.date().isoformat())
        return (_TEXT, value.isoformat(sep="T"))
    if isinstance(value, date):
        return (_TEXT, value.isoformat())
    text = str(value)
    if _MONTH_LABEL.match(text):
        return (_TEXT, f"{text}-01")
    midnight = _MIDNIGHT.match(text)
    if midnight:
        return (_TEXT, midnight.group(1))
    return (_TEXT, text)


def _close(a: Cell, b: Cell, options: CompareOptions) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] != _NUM:
        return a[1] == b[1]
    x, y = a[1], b[1]
    if not isinstance(x, Decimal) or not isinstance(y, Decimal) or x.is_nan() or y.is_nan():
        return False
    tolerance = max(options.abs_tol, options.rel_tol * max(abs(x), abs(y)))
    return abs(x - y) <= tolerance


def _sort_key(cells: Sequence[Cell]) -> tuple[tuple[int, Decimal, str], ...]:
    # numbers sort numerically, everything else by text; the kind keeps them apart
    return tuple(
        (kind, v, "") if isinstance(v, Decimal) else (kind, Decimal(0), str(v)) for kind, v in cells
    )


def _rows_close(
    expected: Sequence[Sequence[Cell]], actual: Sequence[Sequence[Cell]], options: CompareOptions
) -> bool:
    if not options.order_matters:
        expected = sorted(expected, key=_sort_key)
        actual = sorted(actual, key=_sort_key)
    return all(
        all(_close(e, a, options) for e, a in zip(er, ar, strict=True))
        for er, ar in zip(expected, actual, strict=True)
    )


def _column(rows: Sequence[Sequence[Cell]], index: int) -> list[tuple[Cell]]:
    return [(row[index],) for row in rows]


def _scaled(cell: Cell, scale: Decimal) -> Cell:
    kind, value = cell
    return (kind, value * scale) if isinstance(value, Decimal) and scale != 1 else cell


# (generated column index, scale applied to it)
Pick = tuple[int, Decimal]


def _assignments(candidates: list[list[Pick]]) -> Iterable[tuple[Pick, ...]]:
    """Every way to give each reference column a distinct generated column."""

    def walk(i: int, used: tuple[Pick, ...]) -> Iterable[tuple[Pick, ...]]:
        if i == len(candidates):
            yield used
            return
        taken = {k for k, _ in used}
        for pick in candidates[i]:
            if pick[0] not in taken:
                yield from walk(i + 1, (*used, pick))

    return walk(0, ())


def compare(expected: Table, actual: Table, options: CompareOptions | None = None) -> Comparison:
    options = options or CompareOptions()
    n_ref, n_gen = len(expected.columns), len(actual.columns)
    if len(expected.rows) != len(actual.rows):
        return Comparison(
            False, f"row count differs: expected {len(expected.rows)}, got {len(actual.rows)}"
        )
    if n_gen < n_ref:
        return Comparison(False, f"too few columns: expected {n_ref}, got {n_gen}")
    if n_gen > n_ref and not options.allow_extra_columns:
        return Comparison(False, f"extra columns: expected {n_ref}, got {n_gen}")

    ref = [tuple(normalise(v) for v in row) for row in expected.rows]
    gen = [tuple(normalise(v) for v in row) for row in actual.rows]

    scales = (Decimal(1), Decimal("0.01")) if options.allow_percent else (Decimal(1),)
    views = {sc: [tuple(_scaled(c, sc) for c in row) for row in gen] for sc in scales}

    # candidate generated columns for each reference column, judged column by column
    candidates = [
        [
            (k, sc)
            for k in range(n_gen)
            for sc in scales
            if _rows_close(_column(ref, j), _column(views[sc], k), options)
        ]
        for j in range(n_ref)
    ]
    for j, found in enumerate(candidates):
        if not found:
            name = expected.columns[j].name
            return Comparison(False, f"no generated column matches reference column {name!r}")

    for mapping in _assignments(candidates):
        projected = [tuple(views[sc][r][k] for k, sc in mapping) for r in range(len(gen))]
        if _rows_close(ref, projected, options):
            return Comparison(True, "match", tuple(k for k, _ in mapping), n_gen - n_ref)
    return Comparison(False, "every column matches on its own, but the rows do not line up")
