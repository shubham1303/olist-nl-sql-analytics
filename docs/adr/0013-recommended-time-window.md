# 0013. 2017-01 to 2018-08 is a recommended window, not an automatic filter

- Status: Accepted
- Date: 2026-09-23

## Context

Purchases span 2016-09-04 to 2018-10-17, but monthly volume is only complete from
2017-01 through 2018-08:
- 2016 is sparse: 4 orders in September, none at all in November, 1 in December.
- September and October 2018 have 20 orders combined.

Trends or period comparisons that include those months are misleading. Silently
removing them would change the question the user actually asked.

## Decision

- **2017-01-01 to 2018-08-31 is the recommended window** for trends and period
  comparisons. The catalog documents it for the model.
- **Generated SQL is never filtered to this range automatically.** Questions without a
  period use all data, and the answer can point out incomplete months.
- **An explicitly requested period is kept exactly as asked**, even when it falls
  partly or wholly outside the recommended window. The response then states the
  data-quality caveat, for example "2016 contains only 329 orders and no data for
  November".
- When the model applies the recommended window on its own initiative, for example for
  "monthly trend", it must state that as an assumption (ADR 0005). It must never do so
  silently.

## Consequences

- Answers stay faithful to the question, with no hidden filtering.
- The UI needs to show data-quality caveats alongside assumptions and metric
  definitions (Phase 6).
- The evaluation benchmark should include at least one question that deliberately
  touches 2016 or late 2018, to check that the period is preserved and the caveat is
  given.
