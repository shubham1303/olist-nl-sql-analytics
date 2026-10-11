# Eval run `20261009T083443Z_test_us-anthropic-claude-sonnet-4-6`

> **Held-out checkpoint run.** Reason: end of phase 4 baseline

| | |
|---|---|
| Split | test |
| Started | 2026-10-09T08:34:43+00:00 |
| Git commit | `26e75c4ecaa30c98539e3ca0bba33206ba25a63c` (uncommitted changes) |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v1 |
| Benchmark hash | `1acbe02242239bd1` |
| Items | 20 (20 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 20/20 | 100.0% |
| Passed validation | 20/20 | 100.0% |
| Executed | 20/20 | 100.0% |
| **Correct result** | **19/20** | **95.0%** |

## Supporting metrics

- Repair rate: 5.0%; repairs that ended correct: 100.0%
- Latency p50 / p95: 2719.53 / 5163.28 ms
- Tokens per question (input incl. cached + output): 7258.3; output only: 255.2; input served from cache: 88.8%
- Model calls per question: 1.05

| Difficulty | Correct |
|---|---:|
| easy | 6/6 |
| medium | 7/8 |
| hard | 6/6 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 19 |
| wrong_filter_or_time_window | 1 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| test-001 | easy | answered | yes |  | correct |  | 2533 |
| test-002 | easy | answered | yes |  | correct |  | 3370 |
| test-003 | easy | answered | yes |  | correct |  | 2168 |
| test-004 | medium | answered | yes |  | correct |  | 2228 |
| test-005 | medium | answered | yes |  | correct |  | 2076 |
| test-006 | medium | answered | yes |  | correct |  | 3065 |
| test-007 | hard | answered | yes |  | correct |  | 3027 |
| test-008 | medium | answered | yes |  | correct |  | 3184 |
| test-009 | easy | answered | yes |  | correct |  | 2200 |
| test-010 | easy | answered | yes |  | correct |  | 3042 |
| test-011 | hard | answered | yes |  | correct |  | 5163 |
| test-012 | medium | answered | yes |  | correct |  | 2518 |
| test-013 | medium | answered | yes |  | correct |  | 3687 |
| test-014 | hard | answered | yes |  | correct |  | 5158 |
| test-015 | medium | answered | yes |  | correct |  | 2031 |
| test-016 | medium | answered | no |  | wrong_filter_or_time_window (triaged) | Averaged item_count over all 99,441 orders (1.13), including the 775 orders with no items and canceled/unavailable ones; | 2534 |
| test-017 | hard | answered | yes |  | correct |  | 4274 |
| test-018 | hard | answered | yes | yes | correct |  | 8430 |
| test-019 | easy | answered | yes |  | correct |  | 2720 |
| test-020 | hard | answered | yes |  | correct |  | 2306 |
