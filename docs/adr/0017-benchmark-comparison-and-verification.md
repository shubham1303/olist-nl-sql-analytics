# 0017. Benchmark result comparison and verification pinning

- Status: Accepted
- Date: 2026-10-08
- Refines [ADR 0006](0006-evaluation-methodology.md): same benchmark, splits and
  metrics. This ADR fixes what "the result matches" means and what a verification
  vouches for.

## Context

ADR 0006 says the comparison ignores column names, ignores row order unless
`order_matters`, and applies a numeric tolerance. That leaves real cases open:

- A model asked for revenue by category often adds an order count. Is that wrong?
- Rates can be returned as `0.0677` or `6.77`. The prompt doesn't say which.
- Months can come back as a `date`, a midnight `timestamp` (`DATE_TRUNC`) or
  `'2017-01'` text (`TO_CHAR`).
- A tolerance loose enough for money rounded to cents (±0.005) is far too loose for a
  ratio around 0.07.
- A verified item can be edited afterwards, silently voiding the human check.

## Decision

**Comparison** (`evaluation/compare.py`):
- Same row count. Each reference column must pair with a *different* generated column
  holding the same values; names and column order are ignored. Pairings are searched
  with backtracking, so two columns with similar values can't steal each other's
  match.
- **Extra generated columns are allowed** by default (`allow_extra_columns`). Missing
  columns fail. Reference SQL therefore returns only the columns the question asks
  for, plus the label column of a breakdown.
- Rows compare as a multiset unless `order_matters` (rankings and time series set it).
- Numbers match within `max(abs_tol, rel_tol × magnitude)`. Defaults: `abs_tol` 0.005
  (rounding to cents), `rel_tol` 1e-6. Integer, numeric and float are all numbers;
  text never equals a number.
- Rate items set `allow_percent` (the reference value ×100 also matches) and
  `abs_tol` 0.0005, which accepts a ratio to 3 decimals or a percentage to 1 decimal.
- Normalised as equal: `date`, midnight `timestamp`, and `'YYYY-MM'` text for the same
  month. Nothing else is normalised (no case folding, no label mapping).

**Verification** (`evaluation/benchmark.py`):
- `verified_hash` is a SHA-256 over the question, reference SQL, comparison options
  and the stored result. An item counts as verified only when the hash matches, so any
  edit to those fields un-verifies it until a person re-runs `verify`.
- `snapshot` keeps verification only when the result is unchanged.
- Notes, tags and difficulty are outside the hash: editing them doesn't void a check.

**Ranked questions** avoid ties at the cut-off (checked when drafting); a tie would
make more than one answer correct.

## Consequences

- Scores are somewhat more lenient than strict execution match (extra columns,
  percent form). The rules are fixed before any model run, so they can't be tuned to
  flatter results, and every leniency is listed here.
- A generated column that matches by coincidence could pass. Multi-column references
  make this unlikely; single-number answers rely on the tolerance being tight.
- Reference SQL is tied to the data build. The integration suite re-runs every
  reference against the database and requires an exact match with its snapshot.
