# Eval run `20261014T010406Z_dev_us-anthropic-claude-sonnet-4-6_r3of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:04:06+00:00 |
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
- Latency p50 / p95: 2289.71 / 4423.08 ms
- Tokens per question (input incl. cached + output): 7015.4; output only: 247.9; input served from cache: 93.5%
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
| dev-001 | easy | answered | yes |  | correct |  | 1441 |
| dev-002 | easy | answered | yes |  | correct |  | 1606 |
| dev-003 | easy | answered | yes |  | correct |  | 1732 |
| dev-004 | easy | answered | yes |  | correct |  | 2160 |
| dev-005 | easy | answered | yes |  | correct |  | 1828 |
| dev-006 | easy | answered | yes |  | correct |  | 1872 |
| dev-007 | medium | answered | yes |  | correct |  | 2748 |
| dev-008 | medium | answered | yes |  | correct |  | 2309 |
| dev-009 | medium | answered | yes |  | correct |  | 2145 |
| dev-010 | medium | answered | yes |  | correct |  | 3655 |
| dev-011 | medium | answered | yes |  | correct |  | 2161 |
| dev-012 | medium | answered | yes |  | correct |  | 4231 |
| dev-013 | medium | answered | yes |  | correct |  | 2103 |
| dev-014 | easy | answered | yes |  | correct |  | 1816 |
| dev-015 | medium | answered | yes |  | correct |  | 3260 |
| dev-016 | medium | answered | yes |  | correct |  | 2801 |
| dev-017 | hard | answered | yes |  | correct |  | 3242 |
| dev-018 | hard | answered | yes |  | correct |  | 2202 |
| dev-019 | medium | answered | yes |  | correct |  | 1767 |
| dev-020 | hard | answered | yes |  | correct |  | 4423 |
| dev-021 | hard | answered | yes |  | correct |  | 3549 |
| dev-022 | easy | answered | yes |  | correct |  | 2066 |
| dev-023 | medium | answered | yes |  | correct |  | 2601 |
| dev-024 | easy | answered | yes |  | correct |  | 2630 |
| dev-025 | medium | answered | yes |  | correct |  | 2067 |
| dev-026 | easy | answered | yes |  | correct |  | 2195 |
| dev-027 | hard | answered | yes |  | correct |  | 2290 |
| dev-028 | easy | answered | yes |  | correct |  | 1594 |
| dev-029 | hard | answered | yes |  | correct |  | 2947 |
| dev-030 | medium | answered | yes |  | correct |  | 1689 |
| dev-031 | medium | answered | yes |  | correct |  | 3066 |
| dev-032 | medium | answered | yes |  | correct |  | 3214 |
| dev-033 | hard | answered | yes |  | correct |  | 4353 |
| dev-034 | hard | answered | yes |  | correct |  | 5093 |
| dev-035 | hard | answered | no |  | ambiguity (triaged) | Same 10 sellers and values as the reference, reported as delay (actual minus estimated, -43.40) instead of lead time (+4 | 4196 |
