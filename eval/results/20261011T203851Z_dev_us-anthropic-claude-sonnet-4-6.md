# Eval run `20261011T203851Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T20:38:51+00:00 |
| Git commit | `b48199207ff0f330d249221597b73898c5c26ff0` |
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
- Latency p50 / p95: 2086.97 / 3158.11 ms
- Tokens per question (input incl. cached + output): 6980.9; output only: 215.7; input served from cache: 90.5%
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
| dev-001 | easy | answered | yes |  | correct |  | 2898 |
| dev-002 | easy | answered | yes |  | correct |  | 2091 |
| dev-003 | easy | answered | yes |  | correct |  | 1591 |
| dev-004 | easy | answered | yes |  | correct |  | 1816 |
| dev-005 | easy | answered | yes |  | correct |  | 1655 |
| dev-006 | easy | answered | yes |  | correct |  | 1780 |
| dev-007 | medium | answered | yes |  | correct |  | 2539 |
| dev-008 | medium | answered | yes |  | correct |  | 2225 |
| dev-009 | medium | answered | yes |  | correct |  | 1934 |
| dev-010 | medium | answered | yes |  | correct |  | 2471 |
| dev-011 | medium | answered | yes |  | correct |  | 1866 |
| dev-012 | medium | answered | yes |  | correct |  | 3033 |
| dev-013 | medium | answered | yes |  | correct |  | 1868 |
| dev-014 | easy | answered | yes |  | correct |  | 1690 |
| dev-015 | medium | answered | yes |  | correct |  | 3099 |
| dev-016 | medium | answered | yes |  | correct |  | 2755 |
| dev-017 | hard | answered | yes |  | correct |  | 2795 |
| dev-018 | hard | answered | yes |  | correct |  | 1801 |
| dev-019 | medium | answered | yes |  | correct |  | 1606 |
| dev-020 | hard | answered | yes |  | correct |  | 3401 |
| dev-021 | hard | answered | yes |  | correct |  | 3158 |
| dev-022 | easy | answered | yes |  | correct |  | 1738 |
| dev-023 | medium | answered | yes |  | correct |  | 2402 |
| dev-024 | easy | answered | yes |  | correct |  | 2267 |
| dev-025 | medium | answered | yes |  | correct |  | 1827 |
| dev-026 | easy | answered | yes |  | correct |  | 2087 |
| dev-027 | hard | answered | yes |  | correct |  | 2117 |
| dev-028 | easy | answered | yes |  | correct |  | 1412 |
| dev-029 | hard | answered | yes |  | correct |  | 2938 |
| dev-030 | medium | answered | yes |  | correct |  | 1643 |
