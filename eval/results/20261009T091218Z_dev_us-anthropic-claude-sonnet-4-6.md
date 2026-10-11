# Eval run `20261009T091218Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-09T09:12:18+00:00 |
| Git commit | `e02df08afdae7248199d383bb90bb9d5fe06f06b` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v2 |
| Benchmark hash | `972c6b129e75e4e1` |
| Items | 30 (30 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 30/30 | 100.0% |
| Passed validation | 30/30 | 100.0% |
| Executed | 30/30 | 100.0% |
| **Correct result** | **30/30** | **100.0%** |

## Supporting metrics

- Repair rate: 3.3%; repairs that ended correct: 100.0%
- Latency p50 / p95: 2730.18 / 6118.5 ms
- Tokens per question (input incl. cached + output): 7233.8; output only: 231.5; input served from cache: 90.4%
- Model calls per question: 1.03

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 13/13 |
| hard | 6/6 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 30 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 2231 |
| dev-002 | easy | answered | yes |  | correct |  | 3319 |
| dev-003 | easy | answered | yes |  | correct |  | 2078 |
| dev-004 | easy | answered | yes |  | correct |  | 1938 |
| dev-005 | easy | answered | yes |  | correct |  | 2037 |
| dev-006 | easy | answered | yes |  | correct |  | 2132 |
| dev-007 | medium | answered | yes |  | correct |  | 3750 |
| dev-008 | medium | answered | yes |  | correct |  | 2800 |
| dev-009 | medium | answered | yes |  | correct |  | 2590 |
| dev-010 | medium | answered | yes |  | correct |  | 3201 |
| dev-011 | medium | answered | yes |  | correct |  | 2758 |
| dev-012 | medium | answered | yes |  | correct |  | 4614 |
| dev-013 | medium | answered | yes |  | correct |  | 2496 |
| dev-014 | easy | answered | yes |  | correct |  | 2086 |
| dev-015 | medium | answered | yes |  | correct |  | 6118 |
| dev-016 | medium | answered | yes |  | correct |  | 5243 |
| dev-017 | hard | answered | yes | yes | correct |  | 7602 |
| dev-018 | hard | answered | yes |  | correct |  | 2366 |
| dev-019 | medium | answered | yes |  | correct |  | 2464 |
| dev-020 | hard | answered | yes |  | correct |  | 4591 |
| dev-021 | hard | answered | yes |  | correct |  | 4190 |
| dev-022 | easy | answered | yes |  | correct |  | 2730 |
| dev-023 | medium | answered | yes |  | correct |  | 3312 |
| dev-024 | easy | answered | yes |  | correct |  | 2984 |
| dev-025 | medium | answered | yes |  | correct |  | 2399 |
| dev-026 | easy | answered | yes |  | correct |  | 2670 |
| dev-027 | hard | answered | yes |  | correct |  | 2764 |
| dev-028 | easy | answered | yes |  | correct |  | 1955 |
| dev-029 | hard | answered | yes |  | correct |  | 5111 |
| dev-030 | medium | answered | yes |  | correct |  | 2181 |
