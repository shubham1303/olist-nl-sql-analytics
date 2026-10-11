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

## Variance check and review-average tolerance (2026-10-11)

**Repeat runs:** three more dev runs on prompt v2 from commit `b481992`
([20261011T203851Z](results/20261011T203851Z_dev_us-anthropic-claude-sonnet-4-6.md),
[20261011T204001Z](results/20261011T204001Z_dev_us-anthropic-claude-sonnet-4-6.md),
[20261011T204110Z](results/20261011T204110Z_dev_us-anthropic-claude-sonnet-4-6.md)).
With the first v2 run, that is four runs: **30, 30, 30, 28** correct. The latter two
records say "uncommitted changes" only because earlier run files were still uncommitted.

- The SQL logic was the same in every run for every item, even where the text varied
  (up to 4 distinct texts for dev-012, dev-020 and dev-029). dev-012 was correct in all 4.
- Both misses (dev-005, dev-013 in 20261011T204110Z) are review-score averages that the
  model rounded to 2 decimals (4.09 vs 4.0864) instead of 4. Their tolerance was 0.0005,
  so a correct answer failed: a scoring artefact, not a model error.

**Change:** review-score averages (dev-005, dev-013, dev-020, test-008, test-011) now use
the default `abs_tol` of 0.005, which accepts rounding to 2 decimals like every other
non-rate value. This is a comparison-rule change found on dev; it is applied to the two
test items for consistency, not because of any test result (test-008 passed the
checkpoint by 0.00001). All five items were re-verified. Rankings stay distinct at 2
decimals (closest pair: dev-020, 4.0031 vs 4.0092). Rates keep 0.0005.

## Human-written items: 34-item dev baseline (2026-10-11)

Seven hand-written questions were added ([ADR 0018](../docs/adr/0018-human-written-benchmark-items.md)):
dev-031 to dev-034 and test-021 to test-023, all verified. No prompt or catalog change.

**New dev baseline** ([20261011T205414Z](results/20261011T205414Z_dev_us-anthropic-claude-sonnet-4-6.md),
prompt v2, clean commit `aea30e3`): **34/34 correct**. Repair rate 2.9% (dev-034: the
first query joined a CTE to `orders` on a path the validator rejects, and the repair
passed). All four new items were answered with the reference's logic, including the
choices the notes flag as ambiguous (any status, revenue customers only, any later
order within 90 days). None needed its tolerance to pass beyond 2-decimal rounding.

Dev is still saturated, so the human-written items did not expose a failure mode.
Later dev comparisons use 34 items.
