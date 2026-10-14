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

## Refinements (2026-10-13, Phase 6)

Two gaps found in dev results, handled inside the same rules:

- **Months as text.** Models often format months with `TO_CHAR(..., 'YYYY-MM')`, which
  arrives as text. Rule 2 treats a text column as time when every value is a
  `YYYY-MM` or `YYYY-MM-DD` label.
- **Series on different scales.** Rule 2 allows up to three numeric series, but revenue
  and order counts on one axis would flatten one of them. When series differ more
  than 10× in scale the line chart becomes small multiples, one panel per series. It
  never uses a second axis.

## Amendment (2026-10-14, Phase 9): headline, takeaways and stats

The redesigned answer view adds text above the chart. All of it is computed from the
result rows in the browser
([summary.ts](../../frontend/src/lib/summary.ts)), never by the model, which still
never sees results (ADR 0002).

- **Bar results:** a headline naming the highest category, and takeaways naming the
  lowest. A share of the total shown appears only when the values add up: not
  rates, averages, scores or days.
- **Line results:** the peak, the change from the first to the last point, and the
  low point.
- **One row with up to 8 columns** (such as a prompt-v3 summary row) is shown as a
  grid of labelled stats instead of a one-row table.
- **Other tables:** a row count.

The wording is neutral ("highest", not "best"), because the SQL decides what the
ranking means. The chart rules above are unchanged, and the table and SQL are always
one tab away.
