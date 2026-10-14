# Eval run `20261014T021835Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T02:18:35+00:00 |
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
- Latency p50 / p95: 2311.8 / 4896.48 ms
- Tokens per question (input incl. cached + output): 7518.7; output only: 257.3; input served from cache: 93.7%
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
| dev-001 | easy | answered | yes |  | correct |  | 2300 |
| dev-002 | easy | answered | yes |  | correct |  | 1713 |
| dev-003 | easy | answered | yes |  | correct |  | 1578 |
| dev-004 | easy | answered | yes |  | correct |  | 1646 |
| dev-005 | easy | answered | yes |  | correct |  | 1547 |
| dev-006 | easy | answered | yes |  | correct |  | 1672 |
| dev-007 | medium | answered | yes |  | correct |  | 2788 |
| dev-008 | medium | answered | yes |  | correct |  | 2312 |
| dev-009 | medium | answered | yes |  | correct |  | 1951 |
| dev-010 | medium | answered | yes |  | correct |  | 2518 |
| dev-011 | medium | answered | yes |  | correct |  | 2202 |
| dev-012 | medium | answered | yes |  | correct |  | 3629 |
| dev-013 | medium | answered | yes |  | correct |  | 1991 |
| dev-014 | easy | answered | yes |  | correct |  | 1668 |
| dev-015 | medium | answered | yes |  | correct |  | 2471 |
| dev-016 | medium | answered | yes |  | correct |  | 2748 |
| dev-017 | hard | answered | yes | yes | correct |  | 5632 |
| dev-018 | hard | answered | yes |  | correct |  | 2806 |
| dev-019 | medium | answered | yes |  | correct |  | 1832 |
| dev-020 | hard | answered | yes |  | correct |  | 3413 |
| dev-021 | hard | answered | yes |  | correct |  | 2638 |
| dev-022 | easy | answered | yes |  | correct |  | 1868 |
| dev-023 | medium | answered | yes |  | correct |  | 2398 |
| dev-024 | easy | answered | yes |  | correct |  | 2182 |
| dev-025 | medium | answered | yes |  | correct |  | 1871 |
| dev-026 | easy | answered | yes |  | correct |  | 2151 |
| dev-027 | hard | answered | yes |  | correct |  | 2480 |
| dev-028 | easy | answered | yes |  | correct |  | 1539 |
| dev-029 | hard | answered | yes |  | correct |  | 2801 |
| dev-030 | medium | answered | yes |  | correct |  | 1912 |
| dev-031 | medium | answered | yes |  | correct |  | 2872 |
| dev-032 | medium | answered | yes |  | correct |  | 3468 |
| dev-033 | hard | answered | yes |  | correct |  | 4227 |
| dev-034 | hard | answered | yes |  | correct |  | 4896 |
| dev-035 | hard | answered | yes |  | correct |  | 3681 |

## Attempts that did not pass

| Item | Attempt | Outcome | Validation codes |
|---|---|---|---|
| dev-017 | generation | rejected | INVALID_JOIN_PATH |

Each attempt's SQL is in the JSON record.
