# Eval run `20261014T011203Z_dev_us-anthropic-claude-sonnet-4-6_r3of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:12:03+00:00 |
| Git commit | `05621fd4578d4220a9df519d63b6c021bdbd2c7c` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v2 |
| Benchmark hash | `f4a28310824490ca` |
| Items | 35 (35 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 35/35 | 100.0% |
| Passed validation | 35/35 | 100.0% |
| Executed | 35/35 | 100.0% |
| **Correct result** | **34/35** | **97.1%** |

## Supporting metrics

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2180.59 / 4640.0 ms
- Tokens per question (input incl. cached + output): 7019.2; output only: 251.7; input served from cache: 93.5%
- Model calls per question: 1.0

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 15/15 |
| hard | 8/9 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 34 |
| wrong_filter_or_time_window | 1 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 1317 |
| dev-002 | easy | answered | yes |  | correct |  | 1962 |
| dev-003 | easy | answered | yes |  | correct |  | 1541 |
| dev-004 | easy | answered | yes |  | correct |  | 1675 |
| dev-005 | easy | answered | yes |  | correct |  | 1648 |
| dev-006 | easy | answered | yes |  | correct |  | 1842 |
| dev-007 | medium | answered | yes |  | correct |  | 2523 |
| dev-008 | medium | answered | yes |  | correct |  | 2181 |
| dev-009 | medium | answered | yes |  | correct |  | 1710 |
| dev-010 | medium | answered | yes |  | correct |  | 3146 |
| dev-011 | medium | answered | yes |  | correct |  | 2154 |
| dev-012 | medium | answered | yes |  | correct |  | 3180 |
| dev-013 | medium | answered | yes |  | correct |  | 1989 |
| dev-014 | easy | answered | yes |  | correct |  | 1685 |
| dev-015 | medium | answered | yes |  | correct |  | 3332 |
| dev-016 | medium | answered | yes |  | correct |  | 2632 |
| dev-017 | hard | answered | no |  | wrong_filter_or_time_window (triaged) | The WHERE purchase_month >= '2018-02-01' sits in the same SELECT as LAG, so January is removed before the window runs an | 3674 |
| dev-018 | hard | answered | yes |  | correct |  | 2133 |
| dev-019 | medium | answered | yes |  | correct |  | 1988 |
| dev-020 | hard | answered | yes |  | correct |  | 3721 |
| dev-021 | hard | answered | yes |  | correct |  | 3571 |
| dev-022 | easy | answered | yes |  | correct |  | 2052 |
| dev-023 | medium | answered | yes |  | correct |  | 2377 |
| dev-024 | easy | answered | yes |  | correct |  | 2276 |
| dev-025 | medium | answered | yes |  | correct |  | 2271 |
| dev-026 | easy | answered | yes |  | correct |  | 2019 |
| dev-027 | hard | answered | yes |  | correct |  | 2175 |
| dev-028 | easy | answered | yes |  | correct |  | 1726 |
| dev-029 | hard | answered | yes |  | correct |  | 2900 |
| dev-030 | medium | answered | yes |  | correct |  | 1707 |
| dev-031 | medium | answered | yes |  | correct |  | 2994 |
| dev-032 | medium | answered | yes |  | correct |  | 4284 |
| dev-033 | hard | answered | yes |  | correct |  | 4640 |
| dev-034 | hard | answered | yes |  | correct |  | 5054 |
| dev-035 | hard | answered | yes |  | correct |  | 4387 |
