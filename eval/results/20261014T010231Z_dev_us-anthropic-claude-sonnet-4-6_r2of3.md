# Eval run `20261014T010231Z_dev_us-anthropic-claude-sonnet-4-6_r2of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:02:31+00:00 |
| Git commit | `0138f28403230c89fa64fe2c9f88e6741acf043b` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v2 |
| Benchmark hash | `ac9ac4e44b758803` |
| Items | 35 (35 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 35/35 | 100.0% |
| Passed validation | 35/35 | 100.0% |
| Executed | 35/35 | 100.0% |
| **Correct result** | **34/35** | **97.1%** |

## Supporting metrics

- Repair rate: 2.9%; repairs that ended correct: 100.0%
- Latency p50 / p95: 2117.33 / 4816.51 ms
- Tokens per question (input incl. cached + output): 7229.2; output only: 258.9; input served from cache: 93.4%
- Model calls per question: 1.03

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 15/15 |
| hard | 8/9 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| ambiguity | 1 |
| correct | 34 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 1347 |
| dev-002 | easy | answered | yes |  | correct |  | 1853 |
| dev-003 | easy | answered | yes |  | correct |  | 1600 |
| dev-004 | easy | answered | yes |  | correct |  | 1718 |
| dev-005 | easy | answered | yes |  | correct |  | 1685 |
| dev-006 | easy | answered | yes |  | correct |  | 1655 |
| dev-007 | medium | answered | yes |  | correct |  | 2651 |
| dev-008 | medium | answered | yes |  | correct |  | 2117 |
| dev-009 | medium | answered | yes |  | correct |  | 1777 |
| dev-010 | medium | answered | yes |  | correct |  | 2588 |
| dev-011 | medium | answered | yes |  | correct |  | 2019 |
| dev-012 | medium | answered | yes |  | correct |  | 3663 |
| dev-013 | medium | answered | yes |  | correct |  | 2045 |
| dev-014 | easy | answered | yes |  | correct |  | 1728 |
| dev-015 | medium | answered | yes |  | correct |  | 3699 |
| dev-016 | medium | answered | yes |  | correct |  | 3143 |
| dev-017 | hard | answered | yes | yes | correct |  | 5778 |
| dev-018 | hard | answered | yes |  | correct |  | 1846 |
| dev-019 | medium | answered | yes |  | correct |  | 1851 |
| dev-020 | hard | answered | yes |  | correct |  | 3610 |
| dev-021 | hard | answered | yes |  | correct |  | 3162 |
| dev-022 | easy | answered | yes |  | correct |  | 2099 |
| dev-023 | medium | answered | yes |  | correct |  | 3396 |
| dev-024 | easy | answered | yes |  | correct |  | 2392 |
| dev-025 | medium | answered | yes |  | correct |  | 2023 |
| dev-026 | easy | answered | yes |  | correct |  | 2050 |
| dev-027 | hard | answered | yes |  | correct |  | 2201 |
| dev-028 | easy | answered | yes |  | correct |  | 1653 |
| dev-029 | hard | answered | yes |  | correct |  | 2928 |
| dev-030 | medium | answered | yes |  | correct |  | 1634 |
| dev-031 | medium | answered | yes |  | correct |  | 2872 |
| dev-032 | medium | answered | yes |  | correct |  | 4329 |
| dev-033 | hard | answered | yes |  | correct |  | 3549 |
| dev-034 | hard | answered | yes |  | correct |  | 4377 |
| dev-035 | hard | answered | no |  | ambiguity (triaged) | Same 10 sellers and values as the reference, reported as delay (actual minus estimated, -43.40) instead of lead time (+4 | 4817 |

## Attempts that did not pass

| Item | Attempt | Outcome | Validation codes |
|---|---|---|---|
| dev-017 | generation | rejected | INVALID_JOIN_PATH |

Each attempt's SQL is in the JSON record.
