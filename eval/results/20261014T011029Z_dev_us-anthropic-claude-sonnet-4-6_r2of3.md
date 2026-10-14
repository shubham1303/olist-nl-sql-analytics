# Eval run `20261014T011029Z_dev_us-anthropic-claude-sonnet-4-6_r2of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:10:29+00:00 |
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
| **Correct result** | **35/35** | **100.0%** |

## Supporting metrics

- Repair rate: 2.9%; repairs that ended correct: 100.0%
- Latency p50 / p95: 2290.47 / 5222.18 ms
- Tokens per question (input incl. cached + output): 7231.8; output only: 261.5; input served from cache: 93.4%
- Model calls per question: 1.03

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 15/15 |
| hard | 9/9 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 35 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 1485 |
| dev-002 | easy | answered | yes |  | correct |  | 1840 |
| dev-003 | easy | answered | yes |  | correct |  | 1579 |
| dev-004 | easy | answered | yes |  | correct |  | 1630 |
| dev-005 | easy | answered | yes |  | correct |  | 1614 |
| dev-006 | easy | answered | yes |  | correct |  | 1886 |
| dev-007 | medium | answered | yes |  | correct |  | 2696 |
| dev-008 | medium | answered | yes |  | correct |  | 2433 |
| dev-009 | medium | answered | yes |  | correct |  | 2691 |
| dev-010 | medium | answered | yes |  | correct |  | 2827 |
| dev-011 | medium | answered | yes |  | correct |  | 1972 |
| dev-012 | medium | answered | yes |  | correct |  | 3481 |
| dev-013 | medium | answered | yes |  | correct |  | 1940 |
| dev-014 | easy | answered | yes |  | correct |  | 1725 |
| dev-015 | medium | answered | yes |  | correct |  | 3254 |
| dev-016 | medium | answered | yes |  | correct |  | 2867 |
| dev-017 | hard | answered | yes | yes | correct |  | 5604 |
| dev-018 | hard | answered | yes |  | correct |  | 1905 |
| dev-019 | medium | answered | yes |  | correct |  | 1932 |
| dev-020 | hard | answered | yes |  | correct |  | 3922 |
| dev-021 | hard | answered | yes |  | correct |  | 3684 |
| dev-022 | easy | answered | yes |  | correct |  | 1984 |
| dev-023 | medium | answered | yes |  | correct |  | 2340 |
| dev-024 | easy | answered | yes |  | correct |  | 2290 |
| dev-025 | medium | answered | yes |  | correct |  | 2005 |
| dev-026 | easy | answered | yes |  | correct |  | 1891 |
| dev-027 | hard | answered | yes |  | correct |  | 2064 |
| dev-028 | easy | answered | yes |  | correct |  | 1514 |
| dev-029 | hard | answered | yes |  | correct |  | 2941 |
| dev-030 | medium | answered | yes |  | correct |  | 1578 |
| dev-031 | medium | answered | yes |  | correct |  | 2562 |
| dev-032 | medium | answered | yes |  | correct |  | 3128 |
| dev-033 | hard | answered | yes |  | correct |  | 4193 |
| dev-034 | hard | answered | yes |  | correct |  | 5222 |
| dev-035 | hard | answered | yes |  | correct |  | 4523 |

## Attempts that did not pass

| Item | Attempt | Outcome | Validation codes |
|---|---|---|---|
| dev-017 | generation | rejected | INVALID_JOIN_PATH |

Each attempt's SQL is in the JSON record.
