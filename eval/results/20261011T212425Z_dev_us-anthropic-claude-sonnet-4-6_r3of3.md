# Eval run `20261011T212425Z_dev_us-anthropic-claude-sonnet-4-6_r3of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T21:24:25+00:00 |
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
- Latency p50 / p95: 2113.63 / 4185.96 ms
- Tokens per question (input incl. cached + output): 7008.7; output only: 241.6; input served from cache: 93.5%
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
| dev-001 | easy | answered | yes |  | correct |  | 1234 |
| dev-002 | easy | answered | yes |  | correct |  | 1633 |
| dev-003 | easy | answered | yes |  | correct |  | 1404 |
| dev-004 | easy | answered | yes |  | correct |  | 1659 |
| dev-005 | easy | answered | yes |  | correct |  | 1592 |
| dev-006 | easy | answered | yes |  | correct |  | 1481 |
| dev-007 | medium | answered | yes |  | correct |  | 2426 |
| dev-008 | medium | answered | yes |  | correct |  | 2163 |
| dev-009 | medium | answered | yes |  | correct |  | 1732 |
| dev-010 | medium | answered | yes |  | correct |  | 2213 |
| dev-011 | medium | answered | yes |  | correct |  | 1796 |
| dev-012 | medium | answered | yes |  | correct |  | 2892 |
| dev-013 | medium | answered | yes |  | correct |  | 2067 |
| dev-014 | easy | answered | yes |  | correct |  | 1651 |
| dev-015 | medium | answered | yes |  | correct |  | 3109 |
| dev-016 | medium | answered | yes |  | correct |  | 2638 |
| dev-017 | hard | answered | yes |  | correct |  | 3133 |
| dev-018 | hard | answered | yes |  | correct |  | 1803 |
| dev-019 | medium | answered | yes |  | correct |  | 1996 |
| dev-020 | hard | answered | yes |  | correct |  | 3650 |
| dev-021 | hard | answered | yes |  | correct |  | 2867 |
| dev-022 | easy | answered | yes |  | correct |  | 4186 |
| dev-023 | medium | answered | yes |  | correct |  | 2356 |
| dev-024 | easy | answered | yes |  | correct |  | 2232 |
| dev-025 | medium | answered | yes |  | correct |  | 1864 |
| dev-026 | easy | answered | yes |  | correct |  | 1904 |
| dev-027 | hard | answered | yes |  | correct |  | 2114 |
| dev-028 | easy | answered | yes |  | correct |  | 1409 |
| dev-029 | hard | answered | yes |  | correct |  | 2664 |
| dev-030 | medium | answered | yes |  | correct |  | 1514 |
| dev-031 | medium | answered | yes |  | correct |  | 2609 |
| dev-032 | medium | answered | yes |  | correct |  | 2919 |
| dev-033 | hard | answered | yes |  | correct |  | 3647 |
| dev-034 | hard | answered | yes |  | correct |  | 5172 |
