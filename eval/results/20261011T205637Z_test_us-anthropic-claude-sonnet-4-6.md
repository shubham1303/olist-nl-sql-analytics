# Eval run `20261011T205637Z_test_us-anthropic-claude-sonnet-4-6`

> **Held-out checkpoint run.** Reason: end of phase 5 (prompt v2, 23 items incl. 3 human-written)

| | |
|---|---|
| Split | test |
| Started | 2026-10-11T20:56:37+00:00 |
| Git commit | `f5f442324aac6f0666524559db946b9b6568e2a6` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v2 |
| Benchmark hash | `a5717f13e1f03048` |
| Items | 23 (23 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 23/23 | 100.0% |
| Passed validation | 22/23 | 95.7% |
| Executed | 22/23 | 95.7% |
| **Correct result** | **20/23** | **87.0%** |

## Supporting metrics

- Repair rate: 4.3%; repairs that ended correct: 0.0%
- Latency p50 / p95: 2282.63 / 4483.5 ms
- Tokens per question (input incl. cached + output): 7353.7; output only: 279.2; input served from cache: 93.4%
- Model calls per question: 1.04

| Difficulty | Correct |
|---|---:|
| easy | 6/6 |
| medium | 7/8 |
| hard | 7/9 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 20 |
| validator_rejection_false | 1 |
| wrong_filter_or_time_window | 2 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| test-001 | easy | answered | yes |  | correct |  | 2164 |
| test-002 | easy | answered | yes |  | correct |  | 2338 |
| test-003 | easy | answered | yes |  | correct |  | 1575 |
| test-004 | medium | answered | yes |  | correct |  | 1903 |
| test-005 | medium | answered | yes |  | correct |  | 1659 |
| test-006 | medium | answered | yes |  | correct |  | 2775 |
| test-007 | hard | answered | yes |  | correct |  | 2283 |
| test-008 | medium | answered | yes |  | correct |  | 2601 |
| test-009 | easy | answered | yes |  | correct |  | 1571 |
| test-010 | easy | answered | yes |  | correct |  | 2222 |
| test-011 | hard | answered | yes |  | correct |  | 3127 |
| test-012 | medium | answered | yes |  | correct |  | 2055 |
| test-013 | medium | answered | yes |  | correct |  | 2507 |
| test-014 | hard | answered | yes |  | correct |  | 4094 |
| test-015 | medium | answered | yes |  | correct |  | 1501 |
| test-016 | medium | answered | no |  | wrong_filter_or_time_window (triaged) | Same as the Phase 4 checkpoint. Averaged item_count over all orders (1.13), including the 775 with no items; reference u | 1930 |
| test-017 | hard | answered | yes |  | correct |  | 3165 |
| test-018 | hard | answered | yes |  | correct |  | 3773 |
| test-019 | easy | answered | yes |  | correct |  | 2154 |
| test-020 | hard | answered | yes |  | correct |  | 1750 |
| test-021 | hard | answered | no |  | wrong_filter_or_time_window (triaged) | Same mechanism as dev-012, despite the prompt v2 rule. ORDER BY monthly revenue DESC without NULLS LAST or a revenue fil | 4484 |
| test-022 | hard | answered | yes |  | correct |  | 3306 |
| test-023 | hard | rejected | no | yes | validator_rejection_false (triaged) | Correct SQL (rn = 1 and rn = 2 CTEs from orders, joined on customer_unique_id, exact elapsed days) rejected as INVALID_J | 6188 |
