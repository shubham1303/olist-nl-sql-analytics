"""Join-path validation and grain (fan-out) analysis over sqlglot scopes.

Model (docs/sql-safety.md, ADR 0014):

* Every source in a scope (catalog relation or derived table/CTE) knows its unique
  keys and the catalog lineage of its columns.
* A join is valid only if every key pair links columns of the same relationship key
  domain, and at least one side is unique on its join columns (no many-to-many).
* A one-to-many join marks every source on the "one" side as duplicated.
* Duplicate-sensitive aggregates (SUM, AVG, COUNT, ...) over a duplicated source are
  rejected. Grouped or single-row derived tables are unique on their group keys, so
  pre-aggregating before joining is accepted.
* Exception: when the join's many side is unique on the join keys plus its GROUP BY
  columns (orders joined to order_sellers, grouped by seller_id), each duplicated row
  occurs at most once per group. Per-entity statistics (AVG, COUNT, ...) are then
  exact; SUM is still rejected, because it would credit every seller with the whole
  order.
* Bridge relations (order_sellers, order_categories) repeat order-level outcomes per
  seller/category (ADR 0011); aggregating those outcomes is only accepted when grouped
  by the bridge's attribution key.

Anything the model cannot classify confidently fails closed.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field

from sqlglot import exp
from sqlglot.optimizer.scope import Scope

from olist_nlsql.sqlsafety.functions import function_name
from olist_nlsql.sqlsafety.policy import ColumnRef, Policy, RelationPolicy
from olist_nlsql.sqlsafety.result import ErrorCode, Issue, ValidationFailure


@dataclass(frozen=True, slots=True)
class ScopeOutput:
    """What a derived table/CTE exposes to the scope that reads it."""

    columns: tuple[str, ...]
    lineage: dict[str, ColumnRef | None]
    unique_keys: tuple[frozenset[str], ...]
    single_row: bool
    dup_columns: frozenset[str]  # outputs already carrying duplicated values


@dataclass(slots=True)
class Source:
    alias: str
    label: str  # for messages: relation name or "subquery <alias>"
    lineage: dict[str, ColumnRef | None]
    unique_keys: tuple[frozenset[str], ...]
    relation: RelationPolicy | None = None  # set for catalog relations
    single_row: bool = False
    dup_columns: frozenset[str] = frozenset()
    duplicated: bool = False
    duplicated_by: str = ""
    # every join that multiplied this source: (many-side alias, its join columns), or
    # (None, ...) for a cause no GROUP BY can undo
    fanned_by: list[tuple[str | None, frozenset[str]]] = field(default_factory=list)

    def unique_on(self, columns: set[str]) -> bool:
        return any(key <= columns for key in self.unique_keys)


# Statistics of one value per entity in each group: exact when each duplicated row
# occurs at most once per group. SUM is left out on purpose (see the module docstring).
_PER_GROUP_STATISTICS = frozenset({"AVG", "COUNT", "STDDEV", "PERCENTILE_CONT"})


@dataclass(frozen=True, slots=True)
class _Aggregate:
    node: exp.Func
    name: str
    sensitive: bool
    distinct: bool
    counts_rows: bool  # COUNT(*) or an argument with no columns
    columns: tuple[exp.Column, ...]
    windowed: bool


def _nodes_in_scope(scope: Scope) -> Iterator[exp.Expr]:
    """Nodes of this scope only: nested SELECTs, set operations and subqueries are pruned."""
    root = scope.expression

    def prune(node: exp.Expr) -> bool:
        return node is not root and isinstance(node, (exp.Select, exp.SetOperation, exp.Subquery))

    for node in root.walk(prune=prune):
        if node is root or not isinstance(node, (exp.Select, exp.SetOperation, exp.Subquery)):
            yield node


def _columns(node: exp.Expr) -> list[exp.Column]:
    def prune(n: exp.Expr) -> bool:
        return isinstance(n, (exp.Select, exp.SetOperation, exp.Subquery))

    return [n for n in node.walk(prune=prune) if isinstance(n, exp.Column)]


def _conjuncts(condition: exp.Expr) -> list[exp.Expr]:
    condition = condition.unnest()
    if isinstance(condition, exp.And):
        return _conjuncts(condition.left) + _conjuncts(condition.right)
    return [condition]


def _is_constant(node: exp.Expr) -> bool:
    if isinstance(node, exp.Neg):
        return _is_constant(node.this)
    if isinstance(node, exp.Interval):
        return node.find(exp.Column) is None
    return isinstance(node, exp.Literal) and not node.is_string


def _shifted_column(node: exp.Expr) -> exp.Column | None:
    """The column in `col + c`, `c + col` or `col - c`, where c is an INTERVAL or a number.

    Adding a constant is one-to-one, so a source unique on col is unique on col + c too:
    that is what makes a previous-month self-join (m.month = p.month + INTERVAL '1 month')
    a safe key equality.
    """
    node = node.unnest()
    if isinstance(node, exp.Add):
        for column, other in ((node.left, node.right), (node.right, node.left)):
            if isinstance(column, exp.Column) and _is_constant(other):
                return column
    if isinstance(node, exp.Sub) and isinstance(node.left, exp.Column) and _is_constant(node.right):
        return node.left
    return None


def _key_equality(predicate: exp.Expr) -> tuple[exp.Column, exp.Column, bool] | None:
    """(column, column, shifted) for `a = b` or `a = b + constant`, else None."""
    if not isinstance(predicate, exp.EQ):
        return None
    left, right = predicate.left, predicate.right
    if isinstance(left, exp.Column) and isinstance(right, exp.Column):
        return left, right, False
    for column, other in ((left, right), (right, left)):
        if isinstance(column, exp.Column) and (inner := _shifted_column(other)) is not None:
            return column, inner, True
    return None


def _fail(code: ErrorCode, message: str, **details: str) -> ValidationFailure:
    return ValidationFailure(Issue(code, message, dict(details)))


@dataclass
class GrainAnalyzer:
    policy: Policy
    warnings: list[Issue] = field(default_factory=list)
    _memo: dict[int, ScopeOutput] = field(default_factory=dict)

    def run(self, scopes: list[Scope]) -> list[Issue]:
        for scope in scopes:
            self._output(scope)
        return self.warnings

    # scopes

    def _output(self, scope: Scope) -> ScopeOutput:
        key = id(scope.expression)
        if key not in self._memo:
            if isinstance(scope.expression, exp.SetOperation):
                self._memo[key] = self._set_operation_output(scope)
            elif isinstance(scope.expression, exp.Select):
                self._memo[key] = self._select_output(scope)
            else:
                raise _fail(
                    ErrorCode.UNSUPPORTED_CONSTRUCT,
                    f"Cannot analyse a {type(scope.expression).__name__} scope.",
                )
        return self._memo[key]

    def _set_operation_output(self, scope: Scope) -> ScopeOutput:
        branches = [self._output(s) for s in scope.set_operation_scopes]
        columns = branches[0].columns
        dup = frozenset(
            name
            for i, name in enumerate(columns)
            if any(i < len(b.columns) and b.columns[i] in b.dup_columns for b in branches)
        )
        # Rows of a UNION have no known key and no traceable lineage.
        return ScopeOutput(columns, dict.fromkeys(columns), (), False, dup)

    def _source(self, scope: Scope, node: exp.Expr) -> Source:
        alias = node.alias_or_name
        source = scope.sources.get(alias)
        if isinstance(source, exp.Table):
            relation = self.policy.relations[source.name]
            return Source(
                alias=alias,
                label=relation.name,
                lineage={c: (relation.name, c) for c in relation.columns},
                unique_keys=(relation.grain_key,),
                relation=relation,
            )
        if isinstance(source, Scope):
            out = self._output(source)
            return Source(
                alias=alias,
                label=f"subquery {alias}",
                lineage=out.lineage,
                unique_keys=out.unique_keys,
                single_row=out.single_row,
                dup_columns=out.dup_columns,
            )
        raise _fail(ErrorCode.UNSUPPORTED_CONSTRUCT, f"Unsupported FROM item {node.sql()!r}.")

    def _select_output(self, scope: Scope) -> ScopeOutput:
        select = scope.expression
        if not isinstance(select, exp.Select):
            raise _fail(ErrorCode.UNSUPPORTED_CONSTRUCT, "Expected a SELECT scope.")
        sources: dict[str, Source] = {}
        from_ = select.args.get("from_")
        if from_ is not None:
            first = self._source(scope, from_.this)
            sources[first.alias] = first
            for join in select.args.get("joins") or []:
                right = self._source(scope, join.this)
                self._join(join, right, sources)
                sources[right.alias] = right

        group = select.args.get("group")
        group_exprs = list(group.expressions) if group else []
        aggregates = self._aggregates(scope)
        aggregated = bool(group_exprs) or any(not a.windowed for a in aggregates)
        for aggregate in aggregates:
            self._check_aggregate(aggregate, sources, group_exprs)

        return self._describe_output(scope, select, sources, group_exprs, aggregated)

    # joins

    def _join(self, join: exp.Join, right: Source, left_sources: dict[str, Source]) -> None:
        on = join.args.get("on")
        if join.kind == "CROSS" or on is None:
            if right.single_row:
                # Every row gets the one row of `right`: harmless unless aggregated over.
                right.duplicated = not all(s.single_row for s in left_sources.values())
                right.duplicated_by = "the CROSS JOIN repeats its single row on every row"
                if right.duplicated:
                    right.fanned_by.append((None, frozenset()))
                return
            raise _fail(
                ErrorCode.INVALID_JOIN_PATH,
                f"{right.label} is joined without a join condition (a cartesian product). "
                "Use JOIN ... ON with the relationship keys. CROSS JOIN is only allowed with "
                "a single-row subquery, for example one that computes a grand total.",
                relation=right.label,
            )

        pairs: list[tuple[exp.Column, exp.Column]] = []  # (left column, right column)
        shifted: set[int] = set()  # indexes into pairs joined as col = col + constant
        left_alias: str | None = None
        for predicate in _conjuncts(on):
            if predicate.find(exp.Select, exp.Subquery):
                raise _fail(
                    ErrorCode.UNSUPPORTED_CONSTRUCT,
                    "Subqueries are not supported inside JOIN ... ON; move them to WHERE.",
                )
            aliases = {c.table for c in _columns(predicate)}
            touches_right = right.alias in aliases
            touches_left = bool(aliases - {right.alias})
            if not (touches_right and touches_left):
                continue  # a filter on one side, e.g. ON ... AND o.is_delivered
            key = _key_equality(predicate)
            if key is None:
                # A condition across both sides that is not a key equality, e.g.
                # ON o.k = c.k AND o.purchased_at > c.first_at. ANDed with the key pairs it
                # can only remove rows, so the cardinality analysis below still holds. A join
                # with no key pair at all is still rejected after the loop.
                continue
            a, b, is_shift = key
            left_col, right_col = (b, a) if a.table == right.alias else (a, b)
            if left_col.table == right.alias or right_col.table != right.alias:
                raise _fail(
                    ErrorCode.INVALID_JOIN_PATH,
                    f"Join condition {predicate.sql('postgres')!r} must compare a column of "
                    f"{right.label} with a column of an earlier relation.",
                )
            if left_alias not in (None, left_col.table):
                raise _fail(
                    ErrorCode.UNSUPPORTED_CONSTRUCT,
                    f"The join to {right.label} references several earlier relations; join each "
                    "relation through a single relationship.",
                )
            left_alias = left_col.table
            if is_shift:
                shifted.add(len(pairs))
            pairs.append((left_col, right_col))

        if not pairs or left_alias is None:
            raise _fail(
                ErrorCode.INVALID_JOIN_PATH,
                f"The join to {right.label} has no key equality, so it is a cartesian product. "
                "Join on the relationship keys from the catalog.",
                relation=right.label,
            )
        left = left_sources[left_alias]
        for index, (left_col, right_col) in enumerate(pairs):
            if index in shifted:
                self._check_shifted_pair(left, left_col, right, right_col)
            else:
                self._check_pair(left, left_col, right, right_col)

        left_cols = {c.name for c, _ in pairs}
        right_cols = {c.name for _, c in pairs}
        right_unique = right.unique_on(right_cols)
        left_unique_in_itself = left.unique_on(left_cols)
        left_unique = left_unique_in_itself and not left.duplicated
        keys = ", ".join(sorted(right_cols))

        if not right_unique and not left_unique:
            if not left_unique_in_itself:
                raise _fail(
                    ErrorCode.INVALID_JOIN_PATH,
                    f"Joining {left.label} and {right.label} on ({keys}) is many-to-many: neither "
                    f"side has one row per ({keys}), so rows multiply. "
                    f"{self._join_advice(left, right)}",
                    left=left.label,
                    right=right.label,
                )
            raise _fail(
                ErrorCode.FANOUT_RISK,
                f"Joining {right.label} multiplies rows that are already multiplied by "
                f"{left.duplicated_by}: both have many rows per ({keys}), so every combination "
                "of their rows is produced. Aggregate one of them to one row per "
                f"({keys}) in a subquery before joining.",
                left=left.label,
                right=right.label,
            )
        if not right_unique:
            reason = f"the one-to-many join to {right.label} on ({keys})"
            for source in left_sources.values():
                source.fanned_by.append((right.alias, frozenset(right_cols)))
                if not source.duplicated:
                    source.duplicated, source.duplicated_by = True, reason
        if not left_unique:
            right.fanned_by.append(
                (None, frozenset()) if left.duplicated else (left.alias, frozenset(left_cols))
            )
            right.duplicated = True
            right.duplicated_by = (
                left.duplicated_by
                if left.duplicated
                else f"the join from {left.label}, which has many rows per ({keys})"
            )

    def _check_pair(
        self, left: Source, left_col: exp.Column, right: Source, right_col: exp.Column
    ) -> None:
        left_ref = left.lineage.get(left_col.name)
        right_ref = right.lineage.get(right_col.name)
        text = f"{left_col.sql('postgres')} = {right_col.sql('postgres')}"
        if left_ref is None or right_ref is None:
            untraced = left_col if left_ref is None else right_col
            raise _fail(
                ErrorCode.INVALID_JOIN_PATH,
                f"Join key {untraced.sql('postgres')!r} is computed, so it cannot be matched to "
                "a catalog relationship. Join on plain key columns.",
                condition=text,
            )
        if not self.policy.same_domain(left_ref, right_ref):
            raise _fail(
                ErrorCode.INVALID_JOIN_PATH,
                f"{text} does not follow a catalog relationship: {left_ref[0]}.{left_ref[1]} and "
                f"{right_ref[0]}.{right_ref[1]} are not related keys. "
                f"{self._join_advice(left, right)}",
                condition=text,
            )

    @staticmethod
    def _check_shifted_pair(
        left: Source, left_col: exp.Column, right: Source, right_col: exp.Column
    ) -> None:
        """`a.k = b.k + constant` is only a key equality when both sides are the same column."""
        left_ref = left.lineage.get(left_col.name)
        if left_ref is None or left_ref != right.lineage.get(right_col.name):
            raise _fail(
                ErrorCode.INVALID_JOIN_PATH,
                f"A shifted join key ({left_col.sql('postgres')} = {right_col.sql('postgres')} "
                "plus a constant) must compare the same column on both sides, e.g. a month "
                "with the previous month of the same monthly subquery.",
                relation=right.label,
            )

    def _join_advice(self, left: Source, right: Source) -> str:
        names = {s.relation.name for s in (left, right) if s.relation is not None}
        if len(names) == 2:
            a, b = sorted(names)
            relationships = self.policy.relationships_between(a, b)
            if relationships:
                r = relationships[0]
                on = " AND ".join(f"{r.one}.{k.one} = {r.many}.{k.many}" for k in r.keys)
                return f"The approved join is {on}."
            return f"There is no approved relationship between {a} and {b}."
        return "Join through the relationship keys listed in the catalog."

    # aggregates

    def _aggregates(self, scope: Scope) -> list[_Aggregate]:
        found: list[_Aggregate] = []
        for node in _nodes_in_scope(scope):
            if not isinstance(node, exp.Func):
                continue
            spec = self.policy.functions.get(function_name(node))
            if spec is None or spec.kind != "aggregate":
                continue
            wrapper = node.parent
            while isinstance(wrapper, (exp.Filter, exp.WithinGroup)):
                wrapper = wrapper.parent
            columns = list(_columns(node))
            if isinstance(node.parent, exp.WithinGroup):
                order = node.parent.args.get("expression")
                if order is not None:
                    columns.extend(_columns(order))
            argument = node.this
            found.append(
                _Aggregate(
                    node=node,
                    name=spec.name,
                    sensitive=spec.duplicate_sensitive,
                    distinct=isinstance(argument, exp.Distinct),
                    counts_rows=isinstance(argument, exp.Star) or not columns,
                    columns=tuple(columns),
                    windowed=isinstance(wrapper, exp.Window),
                )
            )
        return found

    def _grouped_by_attribution(self, source: Source, group_exprs: list[exp.Expr]) -> bool:
        if source.relation is None:
            return False
        grouped = {
            e.name for e in group_exprs if isinstance(e, exp.Column) and e.table == source.alias
        }
        return source.relation.attribution_key <= grouped

    def _check_aggregate(
        self, aggregate: _Aggregate, sources: dict[str, Source], group_exprs: list[exp.Expr]
    ) -> None:
        if not aggregate.sensitive or not sources:
            return
        text = aggregate.node.sql("postgres")
        if aggregate.distinct and aggregate.name == "COUNT":
            return  # COUNT(DISTINCT x) is unaffected by duplicated rows

        if aggregate.counts_rows:
            if all(s.duplicated for s in sources.values()):
                reason = next(iter(sources.values())).duplicated_by
                raise _fail(
                    ErrorCode.FANOUT_RISK,
                    f"{text} counts rows multiplied by {reason}, so it matches no business "
                    "entity. Count a key instead, e.g. COUNT(DISTINCT order_id).",
                    aggregate=text,
                )
            row_sources = [s for s in sources.values() if not s.duplicated]
            if row_sources and all(
                s.relation is not None
                and s.relation.is_bridge
                and not self._grouped_by_attribution(s, group_exprs)
                for s in row_sources
            ):
                bridge = row_sources[0]
                relation = bridge.relation
                key = ", ".join(sorted(relation.attribution_key)) if relation else ""
                raise _fail(
                    ErrorCode.FANOUT_RISK,
                    f"{text} on {bridge.label} counts one row per order and {key}, so an order "
                    f"with several {key} values is counted several times. Group by {key} for "
                    "per-" + key + " counts, or use COUNT(DISTINCT order_id) or the orders view "
                    "for order counts.",
                    aggregate=text,
                    relation=bridge.label,
                )
            return

        for column in aggregate.columns:
            source = sources.get(column.table)
            if source is None:
                continue  # correlated reference to an outer query: constant per row
            col = column.sql("postgres")
            many = self._once_per_group(aggregate, source, sources, group_exprs)
            if many is not None:
                self._check_per_group(aggregate, source, column, many)
            elif source.duplicated or column.name in source.dup_columns:
                reason = source.duplicated_by or "a one-to-many join inside the subquery"
                advice = (
                    f" {aggregate.name}(DISTINCT ...) removes equal values, not duplicated "
                    "rows, so it is not a safe fix."
                    if aggregate.distinct
                    else ""
                )
                raise _fail(
                    ErrorCode.FANOUT_RISK,
                    f"{text} is computed after {reason}, so each {source.label} value of {col} "
                    f"is repeated once per matching row and the result is inflated.{advice} "
                    f"Compute it from {source.label} alone, or aggregate the many-side relation "
                    "to one row per key in a subquery before joining.",
                    aggregate=text,
                    column=col,
                    relation=source.label,
                )
            relation = source.relation
            if (
                relation is not None
                and column.name in relation.attributed
                and not self._grouped_by_attribution(source, group_exprs)
            ):
                key = ", ".join(sorted(relation.attribution_key))
                raise _fail(
                    ErrorCode.FANOUT_RISK,
                    f"{text}: {col} is an order-level outcome that {relation.name} repeats for "
                    f"every {key} on the order (ADR 0011), so it is only valid per {key}. "
                    f"Add {source.alias}.{key} to GROUP BY, or compute the total from the "
                    "orders view.",
                    aggregate=text,
                    column=col,
                    relation=relation.name,
                )

    def _once_per_group(
        self,
        aggregate: _Aggregate,
        source: Source,
        sources: dict[str, Source],
        group_exprs: list[exp.Expr],
    ) -> Source | None:
        """The many side, when each row of the duplicated `source` occurs at most once per group.

        That holds when one join multiplied `source`, and the many side of that join is
        still unduplicated and unique on its join columns plus its GROUP BY columns, as for
        orders joined to order_sellers and grouped by seller_id.
        """
        if (
            not source.duplicated
            or len(source.fanned_by) != 1
            or aggregate.windowed
            or aggregate.distinct
            or not group_exprs
        ):
            return None
        alias, keys = source.fanned_by[0]
        many = sources.get(alias) if alias is not None else None
        if many is None or many.duplicated:
            return None
        grouped = {
            e.name for e in group_exprs if isinstance(e, exp.Column) and e.table == many.alias
        }
        return many if many.unique_on(set(keys) | grouped) else None

    def _check_per_group(
        self, aggregate: _Aggregate, source: Source, column: exp.Column, many: Source
    ) -> None:
        text, col = aggregate.node.sql("postgres"), column.sql("postgres")
        relation = many.relation
        per_entity = (
            f"per {', '.join(sorted(relation.attribution_key))}"
            if relation is not None and relation.is_bridge
            else f"per group of {many.label}"
        )
        ref = source.lineage.get(column.name)
        if (
            relation is not None
            and ref is not None
            and ref[1] in relation.columns
            and ref[1] not in relation.attributed | relation.grain_key
        ):
            raise _fail(
                ErrorCode.FANOUT_RISK,
                f"{text} uses the order-level {col}, but {relation.name} has its own "
                f"{ref[1]} {per_entity}. Use {many.alias}.{ref[1]} instead.",
                aggregate=text,
                column=col,
                relation=relation.name,
            )
        if aggregate.name not in _PER_GROUP_STATISTICS:
            raise _fail(
                ErrorCode.FANOUT_RISK,
                f"{text} gives every matching {many.label} row the whole {source.label} "
                f"value of {col}, so the totals {per_entity} add up to more than the real "
                f"total. Sum a measure of {many.label} itself, or compute the total from "
                f"{source.label} alone.",
                aggregate=text,
                column=col,
                relation=source.label,
            )

    # output

    def _describe_output(
        self,
        scope: Scope,
        select: exp.Select,
        sources: dict[str, Source],
        group_exprs: list[exp.Expr],
        aggregated: bool,
    ) -> ScopeOutput:
        projections = list(select.selects)
        names = tuple(p.alias_or_name for p in projections)
        lineage: dict[str, ColumnRef | None] = {}
        for name, projection in zip(names, projections, strict=True):
            expression = projection.unalias()
            source = sources.get(expression.table) if isinstance(expression, exp.Column) else None
            lineage[name] = (
                source.lineage.get(expression.name)
                if source is not None and isinstance(expression, exp.Column)
                else None
            )

        single_row = aggregated and not group_exprs
        if group_exprs:
            by_expr = {p.unalias(): p.alias_or_name for p in projections}
            mapped = [by_expr.get(e) for e in group_exprs]
            keys: tuple[frozenset[str], ...] = (
                (frozenset(n for n in mapped if n),) if all(mapped) else ()
            )
        elif single_row:
            keys = (frozenset(),)
        elif select.args.get("distinct") is not None:
            keys = (frozenset(names),)
        else:
            keys = tuple(self._carried_keys(sources, projections))

        dup: frozenset[str] = frozenset()
        if not aggregated:
            dup = frozenset(
                name
                for name, projection in zip(names, projections, strict=True)
                if any(self._is_duplicated(c, sources) for c in _columns(projection))
            )
            if dup and scope.is_root:
                self.warnings.append(
                    Issue(
                        ErrorCode.FANOUT_RISK,
                        "Rows are repeated by a one-to-many join, so these columns show the "
                        f"same value on several rows: {', '.join(sorted(dup))}. Do not add them "
                        "up from this result.",
                        {"columns": ", ".join(sorted(dup))},
                    )
                )
        return ScopeOutput(names, lineage, keys, single_row, dup)

    @staticmethod
    def _is_duplicated(column: exp.Column, sources: dict[str, Source]) -> bool:
        source = sources.get(column.table)
        return source is not None and (source.duplicated or column.name in source.dup_columns)

    @staticmethod
    def _carried_keys(
        sources: dict[str, Source], projections: list[exp.Expr]
    ) -> Iterator[frozenset[str]]:
        """Keys of non-duplicated sources survive a row-level SELECT if fully projected."""
        for source in sources.values():
            if source.duplicated:
                continue
            projected: dict[str, str] = {}
            for projection in projections:
                column = projection.unalias()
                if isinstance(column, exp.Column) and column.table == source.alias:
                    projected[column.name] = projection.alias_or_name
            for key in source.unique_keys:
                if key <= projected.keys():
                    yield frozenset(projected[c] for c in key)


__all__ = ["GrainAnalyzer", "ScopeOutput"]
