# Eval run `20261014T010059Z_dev_us-anthropic-claude-sonnet-4-6_r1of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:00:59+00:00 |
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

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2352.17 / 4095.74 ms
- Tokens per question (input incl. cached + output): 7018.3; output only: 250.8; input served from cache: 90.9%
- Model calls per question: 1.0

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
| dev-001 | easy | answered | yes |  | correct |  | 2378 |
| dev-002 | easy | answered | yes |  | correct |  | 1785 |
| dev-003 | easy | answered | yes |  | correct |  | 1725 |
| dev-004 | easy | answered | yes |  | correct |  | 1612 |
| dev-005 | easy | answered | yes |  | correct |  | 1735 |
| dev-006 | easy | answered | yes |  | correct |  | 1616 |
| dev-007 | medium | answered | yes |  | correct |  | 2722 |
| dev-008 | medium | answered | yes |  | correct |  | 2352 |
| dev-009 | medium | answered | yes |  | correct |  | 2002 |
| dev-010 | medium | answered | yes |  | correct |  | 2501 |
| dev-011 | medium | answered | yes |  | correct |  | 2167 |
| dev-012 | medium | answered | yes |  | correct |  | 3222 |
| dev-013 | medium | answered | yes |  | correct |  | 2070 |
| dev-014 | easy | answered | yes |  | correct |  | 1820 |
| dev-015 | medium | answered | yes |  | correct |  | 2954 |
| dev-016 | medium | answered | yes |  | correct |  | 2912 |
| dev-017 | hard | answered | yes |  | correct |  | 3381 |
| dev-018 | hard | answered | yes |  | correct |  | 1966 |
| dev-019 | medium | answered | yes |  | correct |  | 2005 |
| dev-020 | hard | answered | yes |  | correct |  | 3901 |
| dev-021 | hard | answered | yes |  | correct |  | 3962 |
| dev-022 | easy | answered | yes |  | correct |  | 1956 |
| dev-023 | medium | answered | yes |  | correct |  | 2371 |
| dev-024 | easy | answered | yes |  | correct |  | 2290 |
| dev-025 | medium | answered | yes |  | correct |  | 2356 |
| dev-026 | easy | answered | yes |  | correct |  | 2065 |
| dev-027 | hard | answered | yes |  | correct |  | 2230 |
| dev-028 | easy | answered | yes |  | correct |  | 1652 |
| dev-029 | hard | answered | yes |  | correct |  | 3924 |
| dev-030 | medium | answered | yes |  | correct |  | 1929 |
| dev-031 | medium | answered | yes |  | correct |  | 2952 |
| dev-032 | medium | answered | yes |  | correct |  | 2770 |
| dev-033 | hard | answered | yes |  | correct |  | 3997 |
| dev-034 | hard | answered | yes |  | correct |  | 5174 |
| dev-035 | hard | answered | no |  | ambiguity (triaged) | Same 10 sellers and values as the reference, reported as delay (actual minus estimated, -43.40) instead of lead time (+4 | 4096 |
