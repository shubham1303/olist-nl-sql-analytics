# Eval run `20261011T204001Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T20:40:01+00:00 |
| Git commit | `b48199207ff0f330d249221597b73898c5c26ff0` (uncommitted changes) |
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

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 1935.19 / 3315.53 ms
- Tokens per question (input incl. cached + output): 6980.8; output only: 215.6; input served from cache: 93.6%
- Model calls per question: 1.0

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
| dev-001 | easy | answered | yes |  | correct |  | 1814 |
| dev-002 | easy | answered | yes |  | correct |  | 1647 |
| dev-003 | easy | answered | yes |  | correct |  | 1492 |
| dev-004 | easy | answered | yes |  | correct |  | 1600 |
| dev-005 | easy | answered | yes |  | correct |  | 1797 |
| dev-006 | easy | answered | yes |  | correct |  | 1456 |
| dev-007 | medium | answered | yes |  | correct |  | 2998 |
| dev-008 | medium | answered | yes |  | correct |  | 2059 |
| dev-009 | medium | answered | yes |  | correct |  | 2108 |
| dev-010 | medium | answered | yes |  | correct |  | 2600 |
| dev-011 | medium | answered | yes |  | correct |  | 1892 |
| dev-012 | medium | answered | yes |  | correct |  | 3283 |
| dev-013 | medium | answered | yes |  | correct |  | 1943 |
| dev-014 | easy | answered | yes |  | correct |  | 1532 |
| dev-015 | medium | answered | yes |  | correct |  | 2864 |
| dev-016 | medium | answered | yes |  | correct |  | 2635 |
| dev-017 | hard | answered | yes |  | correct |  | 2984 |
| dev-018 | hard | answered | yes |  | correct |  | 1760 |
| dev-019 | medium | answered | yes |  | correct |  | 1611 |
| dev-020 | hard | answered | yes |  | correct |  | 3423 |
| dev-021 | hard | answered | yes |  | correct |  | 3316 |
| dev-022 | easy | answered | yes |  | correct |  | 1832 |
| dev-023 | medium | answered | yes |  | correct |  | 2141 |
| dev-024 | easy | answered | yes |  | correct |  | 2110 |
| dev-025 | medium | answered | yes |  | correct |  | 1743 |
| dev-026 | easy | answered | yes |  | correct |  | 1935 |
| dev-027 | hard | answered | yes |  | correct |  | 2029 |
| dev-028 | easy | answered | yes |  | correct |  | 1556 |
| dev-029 | hard | answered | yes |  | correct |  | 2813 |
| dev-030 | medium | answered | yes |  | correct |  | 1530 |
