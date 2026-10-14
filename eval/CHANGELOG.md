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

## End-of-phase held-out checkpoint (2026-10-11)

[20261011T205637Z](results/20261011T205637Z_test_us-anthropic-claude-sonnet-4-6.md),
prompt v2, clean commit `f5f4423`: **20/23 correct**.

| Item set | Phase 4 checkpoint (v1) | This checkpoint (v2) |
|---|---:|---:|
| Original 20 items | 19/20 | 19/20 |
| Human-written 3 items | — | 1/3 |

- **test-016** (original): same miss as Phase 4, `wrong_filter_or_time_window`.
- **test-021** (human-written): ranked months by `SUM(revenue) DESC` without `NULLS LAST`,
  so 2018-10 (NULL revenue) came first. Same mechanism as dev-012; the v2 rule did not
  carry over to this case.
- **test-023** (human-written): correct SQL rejected as `INVALID_JOIN_PATH`, and the
  repair too (`validator_rejection_false`). The validator cannot see that `rn = 1` /
  `rn = 2` filters make each side unique per customer.

Per ADR 0006 none of these motivate a change. The human-written items were harder than
the drafted ones, and that is the main finding: a held-out score from drafted
questions alone overstated accuracy.

## Validator: conditions beside a join key (2026-10-11)

**Driven by:** dev-034, which needed a repair in
[20261011T205414Z](results/20261011T205414Z_dev_us-anthropic-claude-sonnet-4-6.md). Run
records keep only the final SQL, so dev-034 was asked six more times through the
pipeline to capture first attempts. Three were rejected:

- **1× `INVALID_JOIN_PATH` (false rejection):**
  `LEFT JOIN orders o ON o.customer_unique_id = fp.customer_unique_id AND o.purchased_at > fp.first_purchased_at AND ...`,
  where `fp` is grouped by customer.
  - The key pair is valid and `fp` is unique on it. The validator rejected every
    condition across both sides that was not a column = column equality.
  - The per-customer CTE was not the problem: the same join with only the key in `ON`
    was already accepted.
  - Moving the range to `WHERE`, as the error suggested, drops cohort members with no
    return, so it changes the answer.
- **2× `PARSE_ERROR`:** a CTE named `returning`, a reserved word that PostgreSQL also
  rejects. That is a correct rejection.

**Change:** conditions in `ON` that are not key equalities are kept as narrowing
conditions when at least one key pair exists ([sql-safety.md](../docs/sql-safety.md)).

- New corpus cases: the dev-034 shape is accepted and also executes in the integration
  suite.
- New cases that stay rejected:
  - a range-only join,
  - items × payments with an extra condition (many-to-many),
  - `SUM(o.revenue)` over orders ⋈ items with an extra condition (`FANOUT_RISK`),
  - a non-key equality beside a key.
- The existing OR-bypass, `<>` and `LOWER(key)` attack cases stay rejected. All 783
  tests pass.

No benchmark run is attached: dev was already 34/34, and the change only removes a
repair round trip on this query shape.

## Multi-run baseline and per-attempt records (2026-10-11)

New tooling ([eval/README.md](README.md#beforeafter-claims)):
- `run --repeat N`.
- `compare`, which reports mean and min over repeated runs with a verdict.
- Run records (version 2) keep every attempt's SQL and validator codes.

**3-run dev baseline** for later comparisons. Prompt v2, validator fix included, clean
commit `b007d43`:
- [r1of3](results/20261011T212143Z_dev_us-anthropic-claude-sonnet-4-6_r1of3.md),
  [r2of3](results/20261011T212304Z_dev_us-anthropic-claude-sonnet-4-6_r2of3.md),
  [r3of3](results/20261011T212425Z_dev_us-anthropic-claude-sonnet-4-6_r3of3.md).
- **34, 34, 34** (mean 34.00, min 34), no repairs, and no attempt failed validation.
- dev-034 passed on its first attempt in all three runs. Before the validator fix, 3 of
  6 re-asks had a rejected first attempt. That fits the fix, but three runs are too few
  to credit it.

## Phase 9: per-seller statistics, delay metric, prompt v3, database probe (2026-10-14)

**Why.** These changes come from 15 questions the owner asked on the live site:
- **Q14**, seller lead time: rejected 3/3 as `FANOUT_RISK`. This was a false rejection.
  The model averaged a per-order CTE column per `seller_id` after joining
  `order_sellers`, and the answer was exact.
- **Q15**, late vs on-time review scores "within the same category and state":
  answered with a 679-row table and no conclusion.
- **Q14** also missed `delivery_delay_days`.

**Changes.**
- **Validator** ([ADR 0014 amendment](../docs/adr/0014-sql-validation-design.md)):
  - Now allowed: `AVG`, `COUNT`, `STDDEV` and `PERCENTILE_CONT` of a one-side value,
    when the join's many side is unique on its join keys plus its `GROUP BY` columns.
  - Still rejected: `SUM`, windowed and `DISTINCT` forms, columns the bridge carries
    per seller, and non-unique groupings.
  - Tests: 11 new corpus cases. The integration suite shows the accepted form equals
    the bridge-only answer row for row, and the rejected `SUM` overstates the total.
- **Catalog:**
  - New metric `average_delivery_delay_days`: −11.8759 days, cross-checked against
    `raw.orders`.
  - Every `delivery_delay_days` column now states its sign.
  - "lead time" stays an alias of `average_delivery_days`, the owner's choice.
- **Prompt v3:** an association question with controls ("within", "controlling
  for") answers with one summary row. That row gives the groups compared, the share of
  groups each way, and the order-weighted difference. On Q15 (local, not a benchmark
  item) it now returns: 257 groups, late orders lower in 100%, a −1.89-star weighted
  gap.
- **API:** `/query` probes the database with `SELECT 1` before the model call, so a
  paused Aurora costs no Bedrock call. This is on for the deployed and local servers
  and off for evaluation runs.

**New baseline under `allow_negated`** (before, clean `05621fd`, prompt v2):
- Runs: [r1](results/20261014T010859Z_dev_us-anthropic-claude-sonnet-4-6_r1of3.md),
  [r2](results/20261014T011029Z_dev_us-anthropic-claude-sonnet-4-6_r2of3.md),
  [r3](results/20261014T011203Z_dev_us-anthropic-claude-sonnet-4-6_r3of3.md).
- Scores: **35, 35, 34**.
- dev-035 is now correct in every run.
- The one miss is dev-017 in r3. The model filtered to February in the same `SELECT`
  as `LAG`, so February came out NULL.

**After** (clean `a6b9f07`, prompt v3):
- Runs: [r1](results/20261014T012433Z_dev_us-anthropic-claude-sonnet-4-6_r1of3.md),
  [r3](results/20261014T021632Z_dev_us-anthropic-claude-sonnet-4-6_r3of3.md),
  [replacement](results/20261014T021835Z_dev_us-anthropic-claude-sonnet-4-6.md).
- Scores: **35, 35, 35**.
- [r2](results/20261014T012604Z_dev_us-anthropic-claude-sonnet-4-6_r2of3.md) scored 28. A local
  network outage made one database query and six Bedrock calls fail with connection
  errors (triaged). It is kept on record but left out of the comparison and replaced
  by one extra run.

**Reading.** `compare` reports "improvement" (mean 34.67 → 35.00, min 34 → 35). The
only item that differs is dev-017 (2/3 → 3/3), which none of these changes targets,
so I read it as **no regression**, not an improvement. The changes target question
shapes the dev split doesn't contain: Q14's join, Q15's summary, and the paused-database
cost.

In two after-runs, dev-017's first attempt self-joined the monthly CTE on
`prev.purchase_month + INTERVAL '1 month'`. That was rejected as `INVALID_JOIN_PATH`
(computed join keys are a documented limitation), and the one repair fixed it both
times.

