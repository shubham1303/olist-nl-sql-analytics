# Accuracy changelog

Phase 5 changes to the catalog, views and prompt, each driven by **dev** failures only
(the test split is never tuned on). Every entry links the dev runs before and after.
Metrics come from the run records.

## Prompt v2: NULL-safe rankings (2026-10-09)

**Driven by:** dev-012 ("Which 10 sellers had the highest revenue in 2018?"), triaged
`wrong_filter_or_time_window` in the baseline. The model summed `revenue` per seller
without a revenue-order filter. Sellers whose 2018 orders were all canceled get NULL
revenue, and PostgreSQL sorts NULLs first under `ORDER BY ... DESC`, so they filled the
top of the ranking. The catalog's "SUM/AVG need no extra filter" holds for totals, not
rankings.

**Change** (commit `e02df08`):
- SQL rule in the prompt: when ranking by an aggregate that can be NULL for some groups,
  filter `is_revenue_order` or add `NULLS LAST`.
- Same caveat on the `revenue` metric in `catalog.yaml`.
- `PROMPT_VERSION` v1 → v2.

**Result** (Sonnet 4.6, same benchmark hash):

| | Baseline v1 ([20261009T082119Z](results/20261009T082119Z_dev_us-anthropic-claude-sonnet-4-6.md)) | v2 ([20261009T091218Z](results/20261009T091218Z_dev_us-anthropic-claude-sonnet-4-6.md)) |
|---|---:|---:|
| Correct | 29/30 | **30/30** |
| Repair rate | 3.3% | 3.3% |
| Latency p50 / p95 (ms) | 2831 / 4959 | 2730 / 6119 |
| Tokens per question | 7,118 | 7,234 |

dev-012 now uses `ORDER BY revenue DESC NULLS LAST` (plus `HAVING SUM(revenue) IS NOT
NULL`). No other item changed outcome. This is one run per prompt version, so a
one-item difference is within run-to-run variation on its own; the generated SQL shows
the rule being applied.
