# 0014. SQL validation: AST-based, fail-closed, catalog-driven and grain-aware

- Status: Accepted
- Date: 2026-09-24

## Context

[ADR 0002](0002-database-is-the-security-boundary.md) makes the read-only database
role the security boundary and the validator a second layer. The validator also has a
job the database can't do: rejecting SQL that is valid and safe but gives a **wrong
business answer**. The classic example is summing order revenue after joining to order
items, which counts each order once per item. Model-generated SQL makes this mistake
often, and it's invisible in the result.

Regex filters are easy to bypass and can't reason about joins. Analysing arbitrary
PostgreSQL semantics isn't feasible either.

## Decision

- **Parse with sqlglot (PostgreSQL dialect)** and validate the syntax tree. Anything
  unparseable, ambiguous or unexpected is rejected. Internal errors are rejected too.
- **Execute only regenerated SQL.** The SQL that runs is re-rendered from the validated
  tree, with relation names schema-qualified and comments dropped. It must re-parse as
  exactly one SELECT, or it is refused. The raw input string never executes.
- **All policy comes from the catalog** ([ADR 0005](0005-curated-analytics-schema-and-catalog.md)):
  exposed relations and columns, relationships, the function allowlist and cast types.
  Settings supply the limits. There is no separate validator config.
- **Allowlists, never denylists.** A query may use only the SELECT constructs, relations,
  columns, functions and cast types that are explicitly allowed.
- **Joins must follow catalog relationships.** Each key pair in a join must link two
  columns from the same relationship key (key domains, derived by union-find over the
  relationships), or the same catalog column. At least one side must be unique on its
  join columns, so many-to-many joins are rejected. `CROSS JOIN` is allowed only with a
  single-row subquery.
- **Cardinality comes from uniqueness, not relationship names.** Catalog relations are
  unique on their grain key. Grouped subqueries are unique on their GROUP BY keys, and
  aggregate subqueries without GROUP BY are single-row. This is what makes
  pre-aggregation before a join acceptable.
- **Fan-out rule.** A one-to-many join marks the "one" side as duplicated.
  Duplicate-sensitive aggregates (SUM, AVG, COUNT, STDDEV, PERCENTILE_CONT) over a
  duplicated source are rejected with `FANOUT_RISK`, and the error explains the fix.
  `COUNT(DISTINCT)`, `MIN` and `MAX` are safe. `SUM(DISTINCT)` is not a fix. Joining a
  second one-to-many relation onto an already duplicated key (items × payments) is
  rejected at the join.
- **Attribution rule** ([ADR 0011](0011-review-and-outcome-attribution.md)). In
  `order_sellers` and `order_categories`, aggregating an attributed order outcome, or
  counting rows, is only allowed when the query groups by the relation's attribution
  key.
- **Row-level repetition is a warning**, not an error, because nothing is aggregated.
- **Limits.** One statement, at most `max_sql_chars` characters and `max_joins` joins.
  An explicit LIMIT above `max_result_rows` is rejected. When no LIMIT is given, the
  validator adds `LIMIT max_result_rows + 1` at the top level only, so the executor can
  report truncation.
- **sqlglot is pinned** to `>=30.19,<31`. Tests guard every behaviour the validator
  relies on, such as function naming and E-string round trips.

## Consequences

- Correct SQL is sometimes rejected, for example an item-weighted average of a product
  attribute. The error names a safe rewrite. The validator deliberately prefers false
  rejections to silently wrong answers.
- Valid SQL can still be analytically wrong in ways the validator doesn't model:
  wrong filters, wrong metric choice, `SUM(revenue) / COUNT(*)`. The evaluation harness
  ([ADR 0006](0006-evaluation-methodology.md)) has to catch those.
- The rules are specific to the curated Olist model: bridge attribution and
  catalog-defined keys. A new relation needs catalog metadata before the validator
  allows it.
- Error codes are stable and messages are written as repair instructions for the
  Phase 3 retry.

## Amendment (2026-10-14): per-group statistics of a one-side value

A live question (seller lead time) joined a per-order CTE to `order_sellers` and
averaged a CTE column per `seller_id`. That was rejected 3/3 as `FANOUT_RISK`, but the
answer was exact: `order_sellers` is unique on `(order_id, seller_id)`, so within each
seller group every order occurs once.

- **Rule.** A duplicated source may feed `AVG`, `COUNT`, `STDDEV` or `PERCENTILE_CONT`
  under three conditions:
  - exactly one join multiplied it;
  - that join's many side is not duplicated itself;
  - the many side is unique on its join columns plus its `GROUP BY` columns.

  The validator records the cause of each duplication, so it can decide this.
- **Still rejected.**
  - `SUM`: it would credit each seller with the whole order.
  - One-side columns the bridge carries per seller: the error names the bridge column.
  - Windowed and `DISTINCT` forms.
  - Grouping by anything not unique, such as `seller_state`.
- **Evidence.** The integration suite checks two things. The accepted per-seller
  average equals the bridge-only answer row for row. The rejected per-seller `SUM`
  adds up to more than the true total.

## Amendment (2026-10-15): NULLS LAST in rankings, shifted self-joins

Two changes, both from dev evidence:

- **NULLS LAST.**
  - The validator now rewrites every query-level `ORDER BY ... DESC` to
    `DESC NULLS LAST`.
  - **Why:** dev-012 ranked months by `SUM(revenue) DESC`, and a month with no
    revenue orders (NULL) came first. Prompt v2's rule against this helps, but a
    rule in the prompt is a request, while the regenerated SQL is a guarantee.
  - **Not changed:** window and `WITHIN GROUP` orderings, and queries whose text
    asks for `NULLS FIRST`. sqlglot parses that the same as a bare `DESC`, so the
    original text decides.
  - It is a rewrite, not an error, and it is visible in the SQL the user sees.
- **Shifted self-joins.**
  - `a.k = b.k + constant` (an `INTERVAL` or a number, or `-`) counts as a key pair
    when `a.k` and `b.k` trace to the same column.
  - **Why:** dev-017's month-over-month self-join was rejected as
    `INVALID_JOIN_PATH` and needed a repair.
  - **Still rejected:** a shift across different columns, or by a non-constant. The
    cardinality and fan-out analysis runs unchanged.
- **Not changed:** two `ROW_NUMBER() ... rn = 1` / `rn = 2` subqueries joined on the
  partition key are still rejected. The only evidence for that false rejection is a
  held-out item (test-023), and ADR 0006 does not allow tuning on held-out results.
  It stays a known limitation in [sql-safety.md](../sql-safety.md) until a dev item
  shows it.

