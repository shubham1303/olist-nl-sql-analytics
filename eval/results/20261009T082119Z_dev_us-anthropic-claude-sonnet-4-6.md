# Eval run `20261009T082119Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-09T08:21:19+00:00 |
| Git commit | `0071a9f5c3bd5ec155fcab15eade4b4c3198766a` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v1 |
| Benchmark hash | `972c6b129e75e4e1` |
| Items | 30 (30 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 30/30 | 100.0% |
| Passed validation | 30/30 | 100.0% |
| Executed | 30/30 | 100.0% |
| **Correct result** | **29/30** | **96.7%** |

## Supporting metrics

- Repair rate: 3.3%; repairs that ended correct: 100.0%
- Latency p50 / p95: 2831.38 / 4958.65 ms
- Tokens per question (input incl. cached + output): 7117.9; output only: 228.4; input served from cache: 90.3%
- Model calls per question: 1.03

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 12/13 |
| hard | 6/6 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 29 |
| wrong_filter_or_time_window | 1 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 2734 |
| dev-002 | easy | answered | yes |  | correct |  | 2328 |
| dev-003 | easy | answered | yes |  | correct |  | 2105 |
| dev-004 | easy | answered | yes |  | correct |  | 2132 |
| dev-005 | easy | answered | yes |  | correct |  | 2380 |
| dev-006 | easy | answered | yes |  | correct |  | 3014 |
| dev-007 | medium | answered | yes |  | correct |  | 3481 |
| dev-008 | medium | answered | yes |  | correct |  | 2934 |
| dev-009 | medium | answered | yes |  | correct |  | 2590 |
| dev-010 | medium | answered | yes |  | correct |  | 3366 |
| dev-011 | medium | answered | yes |  | correct |  | 2592 |
| dev-012 | medium | answered | no |  | wrong_filter_or_time_window (triaged) | No is_revenue_order filter or NULLS LAST, so sellers with NULL 2018 revenue (all orders canceled) sort first in ORDER BY | 4101 |
| dev-013 | medium | answered | yes |  | correct |  | 2444 |
| dev-014 | easy | answered | yes |  | correct |  | 2170 |
| dev-015 | medium | answered | yes |  | correct |  | 2954 |
| dev-016 | medium | answered | yes |  | correct |  | 4141 |
| dev-017 | hard | answered | yes | yes | correct |  | 8726 |
| dev-018 | hard | answered | yes |  | correct |  | 2996 |
| dev-019 | medium | answered | yes |  | correct |  | 2354 |
| dev-020 | hard | answered | yes |  | correct |  | 4959 |
| dev-021 | hard | answered | yes |  | correct |  | 3865 |
| dev-022 | easy | answered | yes |  | correct |  | 4236 |
| dev-023 | medium | answered | yes |  | correct |  | 2984 |
| dev-024 | easy | answered | yes |  | correct |  | 2923 |
| dev-025 | medium | answered | yes |  | correct |  | 2349 |
| dev-026 | easy | answered | yes |  | correct |  | 2473 |
| dev-027 | hard | answered | yes |  | correct |  | 2831 |
| dev-028 | easy | answered | yes |  | correct |  | 1928 |
| dev-029 | hard | answered | yes |  | correct |  | 3683 |
| dev-030 | medium | answered | yes |  | correct |  | 2166 |
