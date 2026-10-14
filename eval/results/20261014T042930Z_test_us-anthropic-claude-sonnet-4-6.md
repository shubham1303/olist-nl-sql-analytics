# Eval run `20261014T042930Z_test_us-anthropic-claude-sonnet-4-6`

> **Held-out checkpoint run.** Reason: Phase 9 end: per-group statistics in the validator, delay metric, prompt v3, database probe

| | |
|---|---|
| Split | test |
| Started | 2026-10-14T04:29:30+00:00 |
| Git commit | `6223ef5bff76d37ec3472982a59471ffa4dd164c` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v3 |
| Benchmark hash | `a5717f13e1f03048` |
| Items | 23 (23 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 23/23 | 100.0% |
| Passed validation | 23/23 | 100.0% |
| Executed | 23/23 | 100.0% |
| **Correct result** | **21/23** | **91.3%** |

## Supporting metrics

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2437.69 / 5071.95 ms
- Tokens per question (input incl. cached + output): 7308.3; output only: 257.3; input served from cache: 93.8%
- Model calls per question: 1.0

| Difficulty | Correct |
|---|---:|
| easy | 6/6 |
| medium | 7/8 |
| hard | 8/9 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 21 |
| wrong_filter_or_time_window | 2 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| test-001 | easy | answered | yes |  | correct |  | 2390 |
| test-002 | easy | answered | yes |  | correct |  | 2438 |
| test-003 | easy | answered | yes |  | correct |  | 1841 |
| test-004 | medium | answered | yes |  | correct |  | 2132 |
| test-005 | medium | answered | yes |  | correct |  | 1755 |
| test-006 | medium | answered | yes |  | correct |  | 2547 |
| test-007 | hard | answered | yes |  | correct |  | 2309 |
| test-008 | medium | answered | yes |  | correct |  | 2905 |
| test-009 | easy | answered | yes |  | correct |  | 2124 |
| test-010 | easy | answered | yes |  | correct |  | 2371 |
| test-011 | hard | answered | yes |  | correct |  | 2964 |
| test-012 | medium | answered | yes |  | correct |  | 2118 |
| test-013 | medium | answered | yes |  | correct |  | 2896 |
| test-014 | hard | answered | yes |  | correct |  | 4088 |
| test-015 | medium | answered | yes |  | correct |  | 1551 |
| test-016 | medium | answered | no |  | wrong_filter_or_time_window (triaged) | Same as the Phase 4 and Phase 5 checkpoints: AVG(item_count) over all orders, including those with no items; the referen | 2483 |
| test-017 | hard | answered | yes |  | correct |  | 3897 |
| test-018 | hard | answered | yes |  | correct |  | 10519 |
| test-019 | easy | answered | yes |  | correct |  | 2291 |
| test-020 | hard | answered | yes |  | correct |  | 2311 |
| test-021 | hard | answered | no |  | wrong_filter_or_time_window (triaged) | Same mechanism as the Phase 5 checkpoint: ORDER BY monthly revenue DESC without NULLS LAST, so a 2018 month with no reve | 5072 |
| test-022 | hard | answered | yes |  | correct |  | 3652 |
| test-023 | hard | answered | yes |  | correct |  | 3534 |
