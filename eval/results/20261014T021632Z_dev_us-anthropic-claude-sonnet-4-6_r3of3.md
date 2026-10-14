# Eval run `20261014T021632Z_dev_us-anthropic-claude-sonnet-4-6_r3of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T02:16:32+00:00 |
| Git commit | `a6b9f079c17f46306bd443d10a34ad19969d8091` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v3 |
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
- Latency p50 / p95: 2830.02 / 5391.21 ms
- Tokens per question (input incl. cached + output): 7521.7; output only: 261.0; input served from cache: 91.1%
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
| dev-001 | easy | answered | yes |  | correct |  | 7019 |
| dev-002 | easy | answered | yes |  | correct |  | 3855 |
| dev-003 | easy | answered | yes |  | correct |  | 3070 |
| dev-004 | easy | answered | yes |  | correct |  | 3852 |
| dev-005 | easy | answered | yes |  | correct |  | 3624 |
| dev-006 | easy | answered | yes |  | correct |  | 3048 |
| dev-007 | medium | answered | yes |  | correct |  | 3203 |
| dev-008 | medium | answered | yes |  | correct |  | 2830 |
| dev-009 | medium | answered | yes |  | correct |  | 2740 |
| dev-010 | medium | answered | yes |  | correct |  | 2847 |
| dev-011 | medium | answered | yes |  | correct |  | 2461 |
| dev-012 | medium | answered | yes |  | correct |  | 4065 |
| dev-013 | medium | answered | yes |  | correct |  | 1938 |
| dev-014 | easy | answered | yes |  | correct |  | 1594 |
| dev-015 | medium | answered | yes |  | correct |  | 3225 |
| dev-016 | medium | answered | yes |  | correct |  | 2750 |
| dev-017 | hard | answered | yes | yes | correct |  | 5391 |
| dev-018 | hard | answered | yes |  | correct |  | 1853 |
| dev-019 | medium | answered | yes |  | correct |  | 1670 |
| dev-020 | hard | answered | yes |  | correct |  | 3752 |
| dev-021 | hard | answered | yes |  | correct |  | 3076 |
| dev-022 | easy | answered | yes |  | correct |  | 1965 |
| dev-023 | medium | answered | yes |  | correct |  | 2521 |
| dev-024 | easy | answered | yes |  | correct |  | 2704 |
| dev-025 | medium | answered | yes |  | correct |  | 1912 |
| dev-026 | easy | answered | yes |  | correct |  | 2112 |
| dev-027 | hard | answered | yes |  | correct |  | 1957 |
| dev-028 | easy | answered | yes |  | correct |  | 1575 |
| dev-029 | hard | answered | yes |  | correct |  | 2730 |
| dev-030 | medium | answered | yes |  | correct |  | 2402 |
| dev-031 | medium | answered | yes |  | correct |  | 2690 |
| dev-032 | medium | answered | yes |  | correct |  | 3157 |
| dev-033 | hard | answered | yes |  | correct |  | 3771 |
| dev-034 | hard | answered | yes |  | correct |  | 4831 |
| dev-035 | hard | answered | yes |  | correct |  | 4027 |

## Attempts that did not pass

| Item | Attempt | Outcome | Validation codes |
|---|---|---|---|
| dev-017 | generation | rejected | INVALID_JOIN_PATH |

Each attempt's SQL is in the JSON record.
