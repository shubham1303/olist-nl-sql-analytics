# Eval run `20261011T212143Z_dev_us-anthropic-claude-sonnet-4-6_r1of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T21:21:43+00:00 |
| Git commit | `b007d43f79bcdc0b6be7e1cdf24fce07e529ca56` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v2 |
| Benchmark hash | `bd2cae1f5670c6a6` |
| Items | 34 (34 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 34/34 | 100.0% |
| Passed validation | 34/34 | 100.0% |
| Executed | 34/34 | 100.0% |
| **Correct result** | **34/34** | **100.0%** |

## Supporting metrics

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2032.5 / 4419.79 ms
- Tokens per question (input incl. cached + output): 7009.4; output only: 242.3; input served from cache: 90.8%
- Model calls per question: 1.0

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 15/15 |
| hard | 8/8 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 34 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 2075 |
| dev-002 | easy | answered | yes |  | correct |  | 1692 |
| dev-003 | easy | answered | yes |  | correct |  | 1574 |
| dev-004 | easy | answered | yes |  | correct |  | 1522 |
| dev-005 | easy | answered | yes |  | correct |  | 1469 |
| dev-006 | easy | answered | yes |  | correct |  | 1602 |
| dev-007 | medium | answered | yes |  | correct |  | 2519 |
| dev-008 | medium | answered | yes |  | correct |  | 1928 |
| dev-009 | medium | answered | yes |  | correct |  | 1824 |
| dev-010 | medium | answered | yes |  | correct |  | 2336 |
| dev-011 | medium | answered | yes |  | correct |  | 2143 |
| dev-012 | medium | answered | yes |  | correct |  | 3303 |
| dev-013 | medium | answered | yes |  | correct |  | 1972 |
| dev-014 | easy | answered | yes |  | correct |  | 1621 |
| dev-015 | medium | answered | yes |  | correct |  | 3155 |
| dev-016 | medium | answered | yes |  | correct |  | 2706 |
| dev-017 | hard | answered | yes |  | correct |  | 3009 |
| dev-018 | hard | answered | yes |  | correct |  | 1807 |
| dev-019 | medium | answered | yes |  | correct |  | 1670 |
| dev-020 | hard | answered | yes |  | correct |  | 3369 |
| dev-021 | hard | answered | yes |  | correct |  | 3229 |
| dev-022 | easy | answered | yes |  | correct |  | 1808 |
| dev-023 | medium | answered | yes |  | correct |  | 2279 |
| dev-024 | easy | answered | yes |  | correct |  | 2080 |
| dev-025 | medium | answered | yes |  | correct |  | 1894 |
| dev-026 | easy | answered | yes |  | correct |  | 1840 |
| dev-027 | hard | answered | yes |  | correct |  | 2032 |
| dev-028 | easy | answered | yes |  | correct |  | 1462 |
| dev-029 | hard | answered | yes |  | correct |  | 2727 |
| dev-030 | medium | answered | yes |  | correct |  | 1547 |
| dev-031 | medium | answered | yes |  | correct |  | 2648 |
| dev-032 | medium | answered | yes |  | correct |  | 3060 |
| dev-033 | hard | answered | yes |  | correct |  | 4872 |
| dev-034 | hard | answered | yes |  | correct |  | 4420 |
