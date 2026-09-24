"""Structured validation results with stable error codes."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class ErrorCode(StrEnum):
    """Stable codes. Messages may change; codes must not."""

    PARSE_ERROR = "PARSE_ERROR"
    MULTIPLE_STATEMENTS = "MULTIPLE_STATEMENTS"
    WRITE_OPERATION = "WRITE_OPERATION"
    UNSUPPORTED_CONSTRUCT = "UNSUPPORTED_CONSTRUCT"
    SELECT_STAR = "SELECT_STAR"
    UNAPPROVED_SCHEMA = "UNAPPROVED_SCHEMA"
    UNAPPROVED_RELATION = "UNAPPROVED_RELATION"
    UNAPPROVED_COLUMN = "UNAPPROVED_COLUMN"
    AMBIGUOUS_COLUMN = "AMBIGUOUS_COLUMN"
    UNAPPROVED_FUNCTION = "UNAPPROVED_FUNCTION"
    INVALID_JOIN_PATH = "INVALID_JOIN_PATH"
    FANOUT_RISK = "FANOUT_RISK"
    RESULT_LIMIT_EXCEEDED = "RESULT_LIMIT_EXCEEDED"
    QUERY_TOO_LARGE = "QUERY_TOO_LARGE"


@dataclass(frozen=True, slots=True)
class Location:
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Issue:
    code: ErrorCode
    message: str  # human-readable; written to be useful as feedback to the SQL generator
    details: Mapping[str, str] = field(default_factory=dict)
    location: Location | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: Literal["accepted", "rejected"]
    # The SQL to execute: regenerated from the validated syntax tree, schema-qualified,
    # with the row limit applied. None when rejected.
    sql: str | None
    errors: tuple[Issue, ...] = ()
    warnings: tuple[Issue, ...] = ()
    limit_applied: bool = False
    relations: tuple[str, ...] = ()  # catalog relations the query reads

    @property
    def ok(self) -> bool:
        return self.status == "accepted"

    @property
    def codes(self) -> tuple[ErrorCode, ...]:
        return tuple(e.code for e in self.errors)


class ValidationFailure(Exception):
    """Internal: raised by a validation stage to stop with one or more issues."""

    def __init__(self, *issues: Issue) -> None:
        super().__init__(issues[0].message if issues else "validation failed")
        self.issues = issues
