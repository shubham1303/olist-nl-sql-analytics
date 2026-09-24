"""AST-based SQL validator: defence in depth in front of the read-only role (ADR 0002).

Pipeline, each stage failing closed:

1. size and parse       one PostgreSQL statement, parsed confidently by sqlglot
2. statement type       SELECT (or UNION of SELECTs) only
3. constructs           no writes anywhere in the tree, no SELECT *, no unsupported syntax
4. functions and casts  catalog allowlist only
5. relations            analytics schema, exposed catalog relations only
6. columns              every column resolves to an exposed catalog column
7. joins and grain      catalog relationships only; no fan-out of aggregated values
8. limits               LIMIT <= max rows; a limit is added when missing

The SQL returned for execution is regenerated from the validated syntax tree with
schema-qualified relation names; the raw input string is never executed.
"""

import difflib
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, OptimizeError, ParseError, TokenError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from olist_nlsql.catalog import Catalog, load_catalog
from olist_nlsql.config import Settings
from olist_nlsql.sqlsafety.functions import STRUCTURAL_FUNCS, function_name
from olist_nlsql.sqlsafety.grain import GrainAnalyzer
from olist_nlsql.sqlsafety.policy import Policy
from olist_nlsql.sqlsafety.result import (
    ErrorCode,
    Issue,
    Location,
    ValidationFailure,
    ValidationResult,
)

DIALECT = "postgres"

_WRITE_STATEMENTS: tuple[type[exp.Expr], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Grant,
    exp.Revoke,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
)
# Statements sqlglot keeps as raw commands that can change state.
_WRITE_COMMANDS = frozenset(
    {"CALL", "DO", "LOCK", "VACUUM", "ANALYZE", "REINDEX", "CLUSTER", "REFRESH", "EXECUTE",
     "PREPARE", "DEALLOCATE", "DISCARD", "LISTEN", "NOTIFY", "UNLISTEN", "RESET", "SAVEPOINT",
     "RELEASE", "IMPORT", "SECURITY", "COMMENT", "START", "END", "ABORT", "CHECKPOINT", "LOAD"}
)  # fmt: skip

_UNSUPPORTED_NODES: dict[type[exp.Expr], str] = {
    exp.Lateral: "LATERAL",
    exp.Values: "VALUES lists",
    exp.TableSample: "TABLESAMPLE",
    exp.Fetch: "FETCH FIRST (use LIMIT)",
    exp.Rollup: "ROLLUP",
    exp.Cube: "CUBE",
    exp.GroupingSets: "GROUPING SETS",
    exp.Intersect: "INTERSECT",
    exp.Except: "EXCEPT",
    exp.Unnest: "UNNEST",
    exp.Parameter: "query parameters",
    exp.Placeholder: "query parameters",
}

_UNRESOLVED = re.compile(r"Column '([^']+)' could not be resolved|Unknown column: (\S+)")
_NOW_FUNCTIONS = frozenset(
    {"CURRENT_DATE", "CURRENT_TIMESTAMP", "NOW", "LOCALTIMESTAMP", "CURRENT_TIME", "AGE"}
)


def _location(node: exp.Expr) -> Location | None:
    for candidate in node.walk():
        meta = candidate.meta if isinstance(candidate, exp.Expr) else {}
        if "line" in meta and "col" in meta:
            return Location(line=int(meta["line"]), column=int(meta["col"]))
    return None


def _issue(code: ErrorCode, message: str, node: exp.Expr | None = None, **details: str) -> Issue:
    return Issue(code, message, dict(details), _location(node) if node is not None else None)


def _identifier(node: exp.Expr | None) -> str:
    """PostgreSQL identifier semantics: unquoted names fold to lower case."""
    if node is None:
        return ""
    if isinstance(node, exp.Identifier):
        return node.name if node.quoted else node.name.lower()
    return node.name.lower()


class SqlValidator:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    @classmethod
    def from_catalog(
        cls, catalog: Catalog | None = None, settings: Settings | None = None
    ) -> "SqlValidator":
        return cls(Policy.from_catalog(catalog or load_catalog(), settings or Settings()))

    # ------------------------------------------------------------------ entry

    def validate(self, sql: str) -> ValidationResult:
        try:
            tree = self._parse(sql)
            self._check_statement(tree)
            self._check_constructs(tree)
            self._check_functions(tree)
            relations = self._check_relations(tree)
            qualified = self._qualify(tree, relations)
            warnings = GrainAnalyzer(self.policy).run(list(traverse_scope(qualified)))
            limit_applied = self._apply_limit(tree)
            self._qualify_relation_names(tree)
            output = tree.sql(dialect=DIALECT, pretty=True, comments=False)
            self._check_round_trip(output)
        except ValidationFailure as failure:
            return ValidationResult(status="rejected", sql=None, errors=failure.issues)
        except Exception as exc:  # anything unexpected must fail closed
            return ValidationResult(
                status="rejected",
                sql=None,
                errors=(
                    Issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        "The query uses a construct the validator cannot analyse safely. "
                        "Rewrite it with plain SELECT, JOIN, WHERE, GROUP BY and ORDER BY.",
                        {"exception": type(exc).__name__},
                    ),
                ),
            )
        return ValidationResult(
            status="accepted",
            sql=output,
            warnings=tuple(warnings),
            limit_applied=limit_applied,
            relations=tuple(sorted(relations)),
        )

    # ---------------------------------------------------------- 1. parse

    def _parse(self, sql: str) -> exp.Expr:
        limit = self.policy.limits.max_sql_chars
        if len(sql) > limit:
            raise ValidationFailure(
                Issue(
                    ErrorCode.QUERY_TOO_LARGE,
                    f"The query is {len(sql)} characters; the maximum is {limit}.",
                    {"length": str(len(sql)), "max": str(limit)},
                )
            )
        if "\x00" in sql:
            raise ValidationFailure(Issue(ErrorCode.PARSE_ERROR, "The query contains a NUL byte."))
        try:
            statements = [
                s for s in sqlglot.parse(sql, read=DIALECT, error_level=ErrorLevel.RAISE) if s
            ]
        except ParseError as exc:
            error = exc.errors[0] if exc.errors else {}
            line, col = error.get("line"), error.get("col")
            location = Location(int(line), int(col)) if line and col else None
            description = error.get("description") or str(exc).splitlines()[0]
            raise ValidationFailure(
                Issue(
                    ErrorCode.PARSE_ERROR,
                    f"The SQL could not be parsed: {description}.",
                    {},
                    location,
                )
            ) from None
        except TokenError as exc:
            raise ValidationFailure(
                Issue(ErrorCode.PARSE_ERROR, f"The SQL could not be tokenized: {exc}.")
            ) from None
        if not statements:
            raise ValidationFailure(Issue(ErrorCode.PARSE_ERROR, "The query is empty."))
        if len(statements) > 1:
            raise ValidationFailure(
                Issue(
                    ErrorCode.MULTIPLE_STATEMENTS,
                    f"Found {len(statements)} statements; exactly one SELECT is allowed.",
                    {"statements": str(len(statements))},
                )
            )
        tree = statements[0]
        if isinstance(tree, exp.Subquery) and isinstance(tree.this, (exp.Select, exp.SetOperation)):
            tree = tree.this  # a parenthesised top-level query
        return tree

    # ---------------------------------------------------------- 2. statement

    def _check_statement(self, tree: exp.Expr) -> None:
        if isinstance(tree, (exp.Select, exp.Union)):
            return
        kind = type(tree).__name__.upper()
        if isinstance(tree, exp.Command):
            kind = str(tree.this).upper()
        if isinstance(tree, _WRITE_STATEMENTS) or kind in _WRITE_COMMANDS:
            raise ValidationFailure(
                _issue(
                    ErrorCode.WRITE_OPERATION,
                    f"{kind} statements are not allowed. "
                    "Only a single read-only SELECT is accepted.",
                    statement=kind,
                )
            )
        raise ValidationFailure(
            _issue(
                ErrorCode.UNSUPPORTED_CONSTRUCT,
                f"{kind} is not supported. Only a single read-only SELECT is accepted.",
                statement=kind,
            )
        )

    # ---------------------------------------------------------- 3. constructs

    def _check_constructs(self, tree: exp.Expr) -> None:
        issues: list[Issue] = []
        joins = 0
        for node in tree.walk():
            if isinstance(node, _WRITE_STATEMENTS):
                issues.append(
                    _issue(
                        ErrorCode.WRITE_OPERATION,
                        f"A {type(node).__name__.upper()} inside the query is not allowed "
                        "(data-modifying CTEs are rejected).",
                        node,
                    )
                )
            elif isinstance(node, exp.Into):
                issues.append(
                    _issue(
                        ErrorCode.WRITE_OPERATION,
                        "SELECT ... INTO creates a table and is not allowed.",
                        node,
                    )
                )
            elif isinstance(node, exp.Lock):
                issues.append(
                    _issue(
                        ErrorCode.WRITE_OPERATION,
                        "FOR UPDATE/SHARE takes row locks and is not allowed.",
                        node,
                    )
                )
            elif isinstance(node, exp.Command):
                issues.append(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        f"Unsupported syntax: {str(node.this)[:40]}.",
                        node,
                    )
                )
            elif type(node) in _UNSUPPORTED_NODES:
                issues.append(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        f"{_UNSUPPORTED_NODES[type(node)]} is not supported.",
                        node,
                    )
                )
            elif isinstance(node, exp.With) and node.args.get("recursive"):
                issues.append(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT, "Recursive CTEs are not supported.", node
                    )
                )
            elif isinstance(node, exp.Distinct) and node.args.get("on") is not None:
                issues.append(
                    _issue(ErrorCode.UNSUPPORTED_CONSTRUCT, "DISTINCT ON is not supported.", node)
                )
            elif isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count):
                issues.append(
                    _issue(
                        ErrorCode.SELECT_STAR,
                        "SELECT * is not allowed. List the columns you need explicitly.",
                        node.parent or node,
                    )
                )
            elif isinstance(node, exp.Table) and not isinstance(node.this, exp.Identifier):
                issues.append(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        "Table functions are not supported in FROM.",
                        node,
                    )
                )
            elif isinstance(node, exp.Join):
                joins += 1
                if node.method:
                    issues.append(
                        _issue(
                            ErrorCode.UNSUPPORTED_CONSTRUCT,
                            f"{node.method} JOIN is not supported; use JOIN ... ON.",
                            node,
                        )
                    )
                if node.side in ("RIGHT", "FULL"):
                    issues.append(
                        _issue(
                            ErrorCode.UNSUPPORTED_CONSTRUCT,
                            f"{node.side} JOIN is not supported; use INNER or LEFT JOIN.",
                            node,
                        )
                    )
        if joins > self.policy.limits.max_joins:
            issues.append(
                Issue(
                    ErrorCode.QUERY_TOO_LARGE,
                    f"The query has {joins} joins; the maximum is {self.policy.limits.max_joins}.",
                    {"joins": str(joins)},
                )
            )
        if issues:
            raise ValidationFailure(*_dedupe(issues))

    # ---------------------------------------------------------- 4. functions

    def _check_functions(self, tree: exp.Expr) -> None:
        issues: list[Issue] = []
        for node in tree.walk():
            if isinstance(node, exp.Dot) and node.find(exp.Func):
                issues.append(
                    _issue(
                        ErrorCode.UNAPPROVED_SCHEMA,
                        "Schema-qualified function calls are not allowed: "
                        f"{node.sql(DIALECT)[:60]}.",
                        node,
                    )
                )
            elif isinstance(node, exp.Cast):
                target = node.args.get("to")
                if (
                    not isinstance(target, exp.DataType)
                    or target.this not in self.policy.cast_types
                ):
                    shown = target.sql(DIALECT) if target is not None else "?"
                    issues.append(
                        _issue(
                            ErrorCode.UNAPPROVED_FUNCTION,
                            f"Casting to {shown} is not allowed. Allowed types: numeric, integer, "
                            "bigint, double precision, text, date, timestamp, boolean, interval.",
                            node,
                            type=shown,
                        )
                    )
            elif isinstance(node, exp.Func) and not isinstance(node, STRUCTURAL_FUNCS):
                name = function_name(node)
                if name in self.policy.functions:
                    continue
                hint = (
                    " The dataset covers 2016-09 to 2018-10; filter with explicit dates instead."
                    if name in _NOW_FUNCTIONS
                    else ""
                )
                issues.append(
                    _issue(
                        ErrorCode.UNAPPROVED_FUNCTION,
                        f"Function {name} is not in the approved function list.{hint}",
                        node,
                        function=name,
                    )
                )
        if issues:
            raise ValidationFailure(*_dedupe(issues))

    # ---------------------------------------------------------- 5. relations

    def _check_relations(self, tree: exp.Expr) -> set[str]:
        catalog_names = set(self.policy.relations) | set(self.policy.hidden_relations)
        issues: list[Issue] = []
        for cte in tree.find_all(exp.CTE):
            if cte.alias.lower() in catalog_names:
                issues.append(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        f"CTE name {cte.alias!r} shadows a catalog relation; choose another name.",
                        cte,
                    )
                )
        if issues:
            raise ValidationFailure(*issues)

        used: set[str] = set()
        accounted: set[int] = set()
        for scope in traverse_scope(tree):
            for node, source in scope.selected_sources.values():
                accounted.add(id(node))
                if isinstance(source, exp.Table):
                    issue = self._check_table(source)
                    if issue is not None:
                        issues.append(issue)
                    else:
                        used.add(_identifier(source.this))
        for table in tree.find_all(exp.Table):
            if id(table) not in accounted:
                issues.append(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        f"Relation reference {table.sql(DIALECT)!r} is in an unsupported position.",
                        table,
                    )
                )
        if issues:
            raise ValidationFailure(*_dedupe(issues))
        return used

    def _check_table(self, table: exp.Table) -> Issue | None:
        schema = _identifier(table.args.get("db"))
        catalog = _identifier(table.args.get("catalog"))
        name = _identifier(table.this)
        available = ", ".join(sorted(self.policy.relations))
        if catalog or (schema and schema != self.policy.schema):
            shown = ".".join(p for p in (catalog, schema, name) if p)
            return _issue(
                ErrorCode.UNAPPROVED_SCHEMA,
                f"{shown} is outside the {self.policy.schema} schema. Only these relations are "
                f"available: {available}.",
                table,
                relation=shown,
            )
        if name in self.policy.relations:
            # Normalise so later stages see the canonical name.
            table.set("this", exp.to_identifier(name))
            return None
        if name in self.policy.hidden_relations:
            return _issue(
                ErrorCode.UNAPPROVED_RELATION,
                f"{name} is not available to queries. {self.policy.hidden_relations[name]}",
                table,
                relation=name,
            )
        return _issue(
            ErrorCode.UNAPPROVED_RELATION,
            f"Unknown relation {name!r}. Available relations: {available}.",
            table,
            relation=name,
        )

    # ---------------------------------------------------------- 6. columns

    def _qualify(self, tree: exp.Expr, relations: set[str]) -> exp.Expr:
        try:
            return qualify(
                tree.copy(),
                schema=self.policy.sqlglot_schema(),
                db=self.policy.schema,
                dialect=DIALECT,
                validate_qualify_columns=True,
                identify=False,
            )
        except OptimizeError as exc:
            raise ValidationFailure(self._column_issue(str(exc), relations)) from None

    def _column_issue(self, message: str, relations: set[str]) -> Issue:
        match = _UNRESOLVED.search(message)
        if match is None:
            return Issue(
                ErrorCode.UNAPPROVED_COLUMN,
                "A column reference could not be resolved to an approved column.",
                {"reason": message[:200]},
            )
        column = (match.group(1) or match.group(2)).split(".")[-1]
        name = column.lower()
        having = sorted(r for r in relations if name in self.policy.relations[r].columns)
        if len(having) > 1:
            return Issue(
                ErrorCode.AMBIGUOUS_COLUMN,
                f"Column {column!r} exists in {', '.join(having)}; qualify it with a table alias.",
                {"column": column, "relations": ", ".join(having)},
            )
        hidden = sorted(r for r in relations if name in self.policy.relations[r].hidden_columns)
        if hidden:
            return Issue(
                ErrorCode.UNAPPROVED_COLUMN,
                f"{hidden[0]}.{name} is not available to queries (it is a lifetime total that "
                "ignores date filters). Compute it from order_items instead.",
                {"column": column, "relation": hidden[0]},
            )
        candidates = sorted({c for r in relations for c in self.policy.relations[r].columns})
        close = difflib.get_close_matches(name, candidates, n=3)
        suggestion = f" Did you mean: {', '.join(close)}?" if close else ""
        scope = ", ".join(sorted(relations)) or "the query"
        return Issue(
            ErrorCode.UNAPPROVED_COLUMN,
            f"Column {column!r} is not an approved column of {scope}.{suggestion}",
            {"column": column},
        )

    # ---------------------------------------------------------- 8. limits

    def _apply_limit(self, tree: exp.Expr) -> bool:
        max_rows = self.policy.limits.max_rows
        for arg in ("limit", "offset"):
            clause = tree.args.get(arg)
            if clause is None:
                continue
            value = clause.args.get("expression")
            if not (isinstance(value, exp.Literal) and value.is_int):
                raise ValidationFailure(
                    _issue(
                        ErrorCode.UNSUPPORTED_CONSTRUCT,
                        f"{arg.upper()} must be a non-negative integer literal.",
                        clause,
                    )
                )
            if arg == "limit" and int(value.this) > max_rows:
                raise ValidationFailure(
                    _issue(
                        ErrorCode.RESULT_LIMIT_EXCEEDED,
                        f"LIMIT {value.this} exceeds the maximum of {max_rows} rows. Use "
                        f"LIMIT {max_rows} or less, or aggregate the result.",
                        clause,
                        limit=str(value.this),
                        max=str(max_rows),
                    )
                )
        if tree.args.get("limit") is not None:
            return False
        # One extra row lets the executor report that the result was truncated.
        tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows + 1)))
        return True

    # ---------------------------------------------------------- output

    def _qualify_relation_names(self, tree: exp.Expr) -> None:
        """Schema-qualify catalog relations so execution never depends on search_path."""
        for scope in traverse_scope(tree):
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table) and not source.args.get("db"):
                    source.set("db", exp.to_identifier(self.policy.schema))

    @staticmethod
    def _check_round_trip(output: str) -> None:
        """The regenerated SQL must re-parse as one SELECT.

        Guards against generator bugs, e.g. sqlglot renders E'\\\\' (one backslash in
        PostgreSQL) as e'\\', an unterminated string. Such output is never executed.
        """
        failure = ValidationFailure(
            Issue(
                ErrorCode.UNSUPPORTED_CONSTRUCT,
                "The query could not be regenerated safely (it contains a literal or construct "
                "the SQL generator does not reproduce faithfully). Simplify string literals.",
            )
        )
        try:
            statements = [s for s in sqlglot.parse(output, read=DIALECT) if s]
        except (ParseError, TokenError):
            raise failure from None
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union)):
            raise failure


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[ErrorCode, str]] = set()
    unique = []
    for issue in issues:
        key = (issue.code, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique
