"""Result comparator rules (ADR 0006): names ignored, order optional, numeric tolerance."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from olist_nlsql.db import ColumnInfo
from olist_nlsql.evaluation.compare import CompareOptions, Table, compare


def table(names: str, *rows: tuple[object, ...]) -> Table:
    return Table(tuple(ColumnInfo(n, "unknown") for n in names.split()), tuple(rows))


REF = table("category revenue", ("a", Decimal("10.00")), ("b", Decimal("20.00")))


def test_identical_tables_match() -> None:
    assert compare(REF, REF).match


def test_column_names_are_ignored() -> None:
    assert compare(REF, table("x y", ("a", Decimal("10.00")), ("b", Decimal("20.00")))).match


def test_column_order_is_ignored() -> None:
    result = compare(REF, table("rev cat", (Decimal("10"), "a"), (Decimal("20"), "b")))
    assert result.match and result.column_map == (1, 0)


def test_row_order_is_ignored_by_default() -> None:
    assert compare(REF, table("c r", ("b", Decimal("20")), ("a", Decimal("10")))).match


def test_row_order_counts_when_order_matters() -> None:
    swapped = table("c r", ("b", Decimal("20")), ("a", Decimal("10")))
    assert not compare(REF, swapped, CompareOptions(order_matters=True)).match


def test_extra_columns_allowed_unless_disabled() -> None:
    extra = table("c r n", ("a", Decimal("10"), 3), ("b", Decimal("20"), 4))
    assert compare(REF, extra).match
    assert compare(REF, extra).extra_columns == 1
    assert not compare(REF, extra, CompareOptions(allow_extra_columns=False)).match


def test_missing_column_fails() -> None:
    result = compare(REF, table("c", ("a",), ("b",)))
    assert not result.match and "too few columns" in result.reason


def test_row_count_must_match() -> None:
    result = compare(REF, table("c r", ("a", Decimal("10"))))
    assert not result.match and "row count" in result.reason


def test_rounding_to_cents_is_within_default_tolerance() -> None:
    ref = table("v", (Decimal("137.4189221886"),))
    assert compare(ref, table("v", (Decimal("137.42"),))).match
    assert not compare(ref, table("v", (Decimal("137.43"),))).match


def test_relative_tolerance_for_large_numbers() -> None:
    ref = table("v", (Decimal("13494400.74"),))
    options = CompareOptions(abs_tol=Decimal(0), rel_tol=Decimal("0.000001"))
    assert compare(ref, table("v", (Decimal("13494401.00"),)), options).match
    assert not compare(ref, table("v", (Decimal("13494500"),)), options).match


def test_integer_float_and_decimal_compare_as_numbers() -> None:
    ref = table("n", (Decimal("625"),))
    assert compare(ref, table("n", (625,))).match
    assert compare(ref, table("n", (625.0,))).match


def test_text_never_matches_a_number() -> None:
    assert not compare(table("n", (Decimal("625"),)), table("n", ("625",))).match


def test_percent_form_only_when_allowed() -> None:
    ref = table("rate", (Decimal("0.0677309"),))
    percent = table("rate", (Decimal("6.77"),))
    rate = CompareOptions(allow_percent=True, abs_tol=Decimal("0.0005"))
    assert compare(ref, percent, rate).match
    assert not compare(ref, percent).match
    assert compare(ref, table("rate", (Decimal("0.0677"),)), rate).match
    assert not compare(ref, table("rate", (Decimal("0.065"),)), rate).match


@pytest.mark.parametrize(
    "generated",
    [date(2017, 1, 1), datetime(2017, 1, 1), "2017-01", "2017-01-01T00:00:00"],
)
def test_month_representations_are_equivalent(generated: object) -> None:
    assert compare(table("m", (date(2017, 1, 1),)), table("m", (generated,))).match


def test_nulls_match_only_nulls() -> None:
    assert compare(table("v", (None,)), table("v", (None,))).match
    assert not compare(table("v", (None,)), table("v", (Decimal(0),))).match


def test_columns_matching_alone_but_not_together_fail() -> None:
    ref = table("a b", (1, "x"), (2, "y"))
    crossed = table("a b", (1, "y"), (2, "x"))
    result = compare(ref, crossed)
    assert not result.match and "do not line up" in result.reason


def test_duplicate_valued_columns_are_resolved_by_backtracking() -> None:
    ref = table("a b", (1, 2), (3, 4))
    # column 0 of the generated table matches both reference columns' values only once
    generated = table("x y z", (2, 1, 2), (4, 3, 9))
    assert compare(ref, generated).match
