# Eval run `20261014T010859Z_dev_us-anthropic-claude-sonnet-4-6_r1of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:08:59+00:00 |
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

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2158.2 / 4441.21 ms
- Tokens per question (input incl. cached + output): 7014.1; output only: 246.6; input served from cache: 93.5%
- Model calls per question: 1.0

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
| dev-001 | easy | answered | yes |  | correct |  | 2100 |
| dev-002 | easy | answered | yes |  | correct |  | 1733 |
| dev-003 | easy | answered | yes |  | correct |  | 1521 |
| dev-004 | easy | answered | yes |  | correct |  | 1601 |
| dev-005 | easy | answered | yes |  | correct |  | 1610 |
| dev-006 | easy | answered | yes |  | correct |  | 2917 |
| dev-007 | medium | answered | yes |  | correct |  | 2690 |
| dev-008 | medium | answered | yes |  | correct |  | 2000 |
| dev-009 | medium | answered | yes |  | correct |  | 1832 |
| dev-010 | medium | answered | yes |  | correct |  | 2279 |
| dev-011 | medium | answered | yes |  | correct |  | 1931 |
| dev-012 | medium | answered | yes |  | correct |  | 3512 |
| dev-013 | medium | answered | yes |  | correct |  | 1894 |
| dev-014 | easy | answered | yes |  | correct |  | 1682 |
| dev-015 | medium | answered | yes |  | correct |  | 3090 |
| dev-016 | medium | answered | yes |  | correct |  | 2526 |
| dev-017 | hard | answered | yes |  | correct |  | 3321 |
| dev-018 | hard | answered | yes |  | correct |  | 2033 |
| dev-019 | medium | answered | yes |  | correct |  | 1647 |
| dev-020 | hard | answered | yes |  | correct |  | 3851 |
| dev-021 | hard | answered | yes |  | correct |  | 2974 |
| dev-022 | easy | answered | yes |  | correct |  | 2016 |
| dev-023 | medium | answered | yes |  | correct |  | 2440 |
| dev-024 | easy | answered | yes |  | correct |  | 2396 |
| dev-025 | medium | answered | yes |  | correct |  | 1866 |
| dev-026 | easy | answered | yes |  | correct |  | 2085 |
| dev-027 | hard | answered | yes |  | correct |  | 2158 |
| dev-028 | easy | answered | yes |  | correct |  | 1632 |
| dev-029 | hard | answered | yes |  | correct |  | 3104 |
| dev-030 | medium | answered | yes |  | correct |  | 1849 |
| dev-031 | medium | answered | yes |  | correct |  | 2943 |
| dev-032 | medium | answered | yes |  | correct |  | 3369 |
| dev-033 | hard | answered | yes |  | correct |  | 4441 |
| dev-034 | hard | answered | yes |  | correct |  | 4870 |
| dev-035 | hard | answered | yes |  | correct |  | 4243 |
