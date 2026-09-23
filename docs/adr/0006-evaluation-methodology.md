# 0006. 50-question benchmark, 30 dev / 20 held-out, verified references

- Status: Accepted
- Date: 2026-09-23

## Context

Accuracy claims are the core of the project's credibility. Tuning prompts against the
same questions you report on inflates results, and unverified "ground truth" makes
metrics meaningless.

## Decision

**Benchmark:**
- 50 questions: **30 development** (`eval/benchmark/dev.yaml`) and **20 held-out test**
  (`eval/benchmark/test.yaml`).
- Questions are spread across easy, medium and hard, and across these areas:
  filtering, aggregations, joins, time series, customer metrics, seller metrics,
  product/category metrics, delivery performance, review metrics, and multi-step
  business questions.

**Each item has:**
- `id`, `question`, `difficulty`, `tags`
- `reference_sql`
- a stored `reference_result` snapshot
- comparison options (`order_matters`, numeric tolerance)
- `verified_by` and `verified_on`

**Verification:**
- AI may help draft questions and reference SQL.
- An item counts as ground truth only after a human has explicitly reviewed its SQL and
  result. Unverified items are excluded from scoring and reported as such.

**Tuning discipline:**
- Only the dev set is used while iterating on prompts, catalog or views.
- The held-out set is run only at checkpoints and never used to motivate a change.
  Every held-out run is recorded (date, git commit, model config), so the number of
  held-out runs is visible.

**Reported metrics** (each separately, on dev and held-out):
- **SQL generation success:** the model returned parseable SQL.
- **Validation success:** the SQL passed the safety validator.
- **Execution success:** the SQL executed without error.
- **Result correctness:** the result matches the reference result. The comparison
  ignores column names, ignores row order unless `order_matters`, and applies a numeric
  tolerance.
- **Held-out answer accuracy:** result correctness on the test set. This is the
  headline number.
- **Supporting metrics:** repair rate, latency p50/p95, and tokens per question.

**Failure categories:**
- generation failure
- validator rejection (split into correct and false rejections)
- execution error
- wrong relation or join
- wrong aggregation
- wrong filter or time window
- wrong metric definition
- ambiguity
- reference error

**Integrity:**
- Accuracy is never estimated or fabricated. Every reported number links to a
  committed results file produced by the harness.

## Consequences

- The benchmark exists before the UI (Phase 4 comes before Phase 6).
- Held-out numbers will likely be lower than dev numbers. That gap is reported, not
  hidden.
- Eval runs cost Bedrock tokens. Runs are manual or on dispatch, not on every push.
