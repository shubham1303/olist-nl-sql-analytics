# Eval run `20261015T222621Z_dev_us-anthropic-claude-sonnet-4-6_r2of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-15T22:26:21+00:00 |
| Git commit | `43fbd65889906ac905abff5cde7d37a76cd202f3` |
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

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2087.44 / 4272.32 ms
- Tokens per question (input incl. cached + output): 7305.0; output only: 254.5; input served from cache: 93.8%
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
| dev-001 | easy | answered | yes |  | correct |  | 1310 |
| dev-002 | easy | answered | yes |  | correct |  | 1659 |
| dev-003 | easy | answered | yes |  | correct |  | 1503 |
| dev-004 | easy | answered | yes |  | correct |  | 1689 |
| dev-005 | easy | answered | yes |  | correct |  | 1508 |
| dev-006 | easy | answered | yes |  | correct |  | 1521 |
| dev-007 | medium | answered | yes |  | correct |  | 2664 |
| dev-008 | medium | answered | yes |  | correct |  | 2057 |
| dev-009 | medium | answered | yes |  | correct |  | 1703 |
| dev-010 | medium | answered | yes |  | correct |  | 2433 |
| dev-011 | medium | answered | yes |  | correct |  | 2087 |
| dev-012 | medium | answered | yes |  | correct |  | 3453 |
| dev-013 | medium | answered | yes |  | correct |  | 1946 |
| dev-014 | easy | answered | yes |  | correct |  | 1723 |
| dev-015 | medium | answered | yes |  | correct |  | 3815 |
| dev-016 | medium | answered | yes |  | correct |  | 3067 |
| dev-017 | hard | answered | yes |  | correct |  | 3108 |
| dev-018 | hard | answered | yes |  | correct |  | 1838 |
| dev-019 | medium | answered | yes |  | correct |  | 2822 |
| dev-020 | hard | answered | yes |  | correct |  | 3358 |
| dev-021 | hard | answered | yes |  | correct |  | 3539 |
| dev-022 | easy | answered | yes |  | correct |  | 1885 |
| dev-023 | medium | answered | yes |  | correct |  | 2339 |
| dev-024 | easy | answered | yes |  | correct |  | 2320 |
| dev-025 | medium | answered | yes |  | correct |  | 1767 |
| dev-026 | easy | answered | yes |  | correct |  | 1996 |
| dev-027 | hard | answered | yes |  | correct |  | 2002 |
| dev-028 | easy | answered | yes |  | correct |  | 1430 |
| dev-029 | hard | answered | yes |  | correct |  | 2806 |
| dev-030 | medium | answered | yes |  | correct |  | 1695 |
| dev-031 | medium | answered | yes |  | correct |  | 3014 |
| dev-032 | medium | answered | yes |  | correct |  | 3417 |
| dev-033 | hard | answered | yes |  | correct |  | 4272 |
| dev-034 | hard | answered | yes |  | correct |  | 5752 |
| dev-035 | hard | answered | yes |  | correct |  | 4198 |
