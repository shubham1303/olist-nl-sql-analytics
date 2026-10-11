# Eval run `20261011T212304Z_dev_us-anthropic-claude-sonnet-4-6_r2of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T21:23:04+00:00 |
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
- Latency p50 / p95: 2034.12 / 4047.65 ms
- Tokens per question (input incl. cached + output): 7011.3; output only: 244.3; input served from cache: 93.5%
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
| dev-001 | easy | answered | yes |  | correct |  | 1381 |
| dev-002 | easy | answered | yes |  | correct |  | 1647 |
| dev-003 | easy | answered | yes |  | correct |  | 1432 |
| dev-004 | easy | answered | yes |  | correct |  | 1553 |
| dev-005 | easy | answered | yes |  | correct |  | 1658 |
| dev-006 | easy | answered | yes |  | correct |  | 1615 |
| dev-007 | medium | answered | yes |  | correct |  | 2460 |
| dev-008 | medium | answered | yes |  | correct |  | 1910 |
| dev-009 | medium | answered | yes |  | correct |  | 2076 |
| dev-010 | medium | answered | yes |  | correct |  | 2326 |
| dev-011 | medium | answered | yes |  | correct |  | 1804 |
| dev-012 | medium | answered | yes |  | correct |  | 3386 |
| dev-013 | medium | answered | yes |  | correct |  | 1894 |
| dev-014 | easy | answered | yes |  | correct |  | 1567 |
| dev-015 | medium | answered | yes |  | correct |  | 2992 |
| dev-016 | medium | answered | yes |  | correct |  | 2987 |
| dev-017 | hard | answered | yes |  | correct |  | 3074 |
| dev-018 | hard | answered | yes |  | correct |  | 1784 |
| dev-019 | medium | answered | yes |  | correct |  | 1697 |
| dev-020 | hard | answered | yes |  | correct |  | 3403 |
| dev-021 | hard | answered | yes |  | correct |  | 2903 |
| dev-022 | easy | answered | yes |  | correct |  | 1837 |
| dev-023 | medium | answered | yes |  | correct |  | 2177 |
| dev-024 | easy | answered | yes |  | correct |  | 2331 |
| dev-025 | medium | answered | yes |  | correct |  | 2110 |
| dev-026 | easy | answered | yes |  | correct |  | 2010 |
| dev-027 | hard | answered | yes |  | correct |  | 2034 |
| dev-028 | easy | answered | yes |  | correct |  | 1402 |
| dev-029 | hard | answered | yes |  | correct |  | 2538 |
| dev-030 | medium | answered | yes |  | correct |  | 1742 |
| dev-031 | medium | answered | yes |  | correct |  | 2602 |
| dev-032 | medium | answered | yes |  | correct |  | 3044 |
| dev-033 | hard | answered | yes |  | correct |  | 4048 |
| dev-034 | hard | answered | yes |  | correct |  | 4965 |
