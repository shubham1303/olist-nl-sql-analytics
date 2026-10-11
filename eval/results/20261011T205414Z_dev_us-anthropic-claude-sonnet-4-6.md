# Eval run `20261011T205414Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T20:54:14+00:00 |
| Git commit | `aea30e35c58cd70978c14bf927646638aabfabca` |
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

- Repair rate: 2.9%; repairs that ended correct: 100.0%
- Latency p50 / p95: 1970.39 / 4430.75 ms
- Tokens per question (input incl. cached + output): 7241.5; output only: 261.6; input served from cache: 90.7%
- Model calls per question: 1.03

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
| dev-001 | easy | answered | yes |  | correct |  | 1970 |
| dev-002 | easy | answered | yes |  | correct |  | 1573 |
| dev-003 | easy | answered | yes |  | correct |  | 1562 |
| dev-004 | easy | answered | yes |  | correct |  | 1552 |
| dev-005 | easy | answered | yes |  | correct |  | 1551 |
| dev-006 | easy | answered | yes |  | correct |  | 1705 |
| dev-007 | medium | answered | yes |  | correct |  | 1827 |
| dev-008 | medium | answered | yes |  | correct |  | 2100 |
| dev-009 | medium | answered | yes |  | correct |  | 1726 |
| dev-010 | medium | answered | yes |  | correct |  | 2366 |
| dev-011 | medium | answered | yes |  | correct |  | 1897 |
| dev-012 | medium | answered | yes |  | correct |  | 3091 |
| dev-013 | medium | answered | yes |  | correct |  | 1952 |
| dev-014 | easy | answered | yes |  | correct |  | 1578 |
| dev-015 | medium | answered | yes |  | correct |  | 2933 |
| dev-016 | medium | answered | yes |  | correct |  | 2811 |
| dev-017 | hard | answered | yes |  | correct |  | 2995 |
| dev-018 | hard | answered | yes |  | correct |  | 1760 |
| dev-019 | medium | answered | yes |  | correct |  | 1601 |
| dev-020 | hard | answered | yes |  | correct |  | 3729 |
| dev-021 | hard | answered | yes |  | correct |  | 2919 |
| dev-022 | easy | answered | yes |  | correct |  | 1852 |
| dev-023 | medium | answered | yes |  | correct |  | 2159 |
| dev-024 | easy | answered | yes |  | correct |  | 2250 |
| dev-025 | medium | answered | yes |  | correct |  | 1850 |
| dev-026 | easy | answered | yes |  | correct |  | 1996 |
| dev-027 | hard | answered | yes |  | correct |  | 1987 |
| dev-028 | easy | answered | yes |  | correct |  | 1478 |
| dev-029 | hard | answered | yes |  | correct |  | 2587 |
| dev-030 | medium | answered | yes |  | correct |  | 1538 |
| dev-031 | medium | answered | yes |  | correct |  | 2706 |
| dev-032 | medium | answered | yes |  | correct |  | 3158 |
| dev-033 | hard | answered | yes |  | correct |  | 4431 |
| dev-034 | hard | answered | yes | yes | correct (triaged) | Correct after one repair. The model's assumption says it rewrote the join to avoid INVALID_JOIN_PATH. Re-asking dev-034  | 9894 |
