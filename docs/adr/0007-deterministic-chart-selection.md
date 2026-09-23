# 0007. Deterministic chart selection from result shape

- Status: Accepted
- Date: 2026-09-23

## Context

The results need an appropriate visualisation. Asking an LLM to pick one adds latency,
cost and non-determinism for a problem that the shape of the result already answers.

## Decision

- The chart is chosen by a pure function in the frontend
  (`frontend/src/charts/selectChart.ts`) from column types, cardinality and row count.
  No LLM call is involved.
- The API returns typed column metadata (`name`, `type`: number, integer, text, date,
  timestamp, boolean) alongside the rows.
- Initial rules, first match wins:
  1. One row with one numeric column → **KPI tile**.
  2. One date/timestamp column and 1–3 numeric columns → **line chart**.
  3. One text column with ≤ 25 distinct values and 1 numeric column → **bar chart**
     (horizontal when the labels are long).
  4. Anything else → **table only**.
- The table is always available. The user can switch to the table view.

## Consequences

- Chart choice is instant, free and unit-testable with fixtures.
- Some results will get a plainer chart than a human would choose. We'll add rules
  when real results show a gap.
