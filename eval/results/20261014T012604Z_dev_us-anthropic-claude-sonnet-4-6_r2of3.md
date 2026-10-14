# Eval run `20261014T012604Z_dev_us-anthropic-claude-sonnet-4-6_r2of3`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-14T01:26:04+00:00 |
| Git commit | `a6b9f079c17f46306bd443d10a34ad19969d8091` |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | region=us-east-1, effort=medium, thinking=disabled, max_output_tokens=4096, timeout_seconds=60 |
| Prompt version | v3 |
| Benchmark hash | `f4a28310824490ca` |
| Items | 35 (35 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 29/35 | 82.9% |
| Passed validation | 29/35 | 82.9% |
| Executed | 28/35 | 80.0% |
| **Correct result** | **28/35** | **80.0%** |

## Supporting metrics

- Repair rate: 2.9%; repairs that ended correct: 100.0%
- Latency p50 / p95: 2035.95 / 1251276.14 ms
- Tokens per question (input incl. cached + output): 6242.9; output only: 192.2; input served from cache: 93.7%
- Model calls per question: 1.03

| Difficulty | Correct |
|---|---:|
| easy | 11/11 |
| medium | 12/15 |
| hard | 5/9 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 28 |
| execution_error | 1 |
| generation_failure | 6 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 1402 |
| dev-002 | easy | answered | yes |  | correct |  | 1687 |
| dev-003 | easy | answered | yes |  | correct |  | 1490 |
| dev-004 | easy | answered | yes |  | correct |  | 1590 |
| dev-005 | easy | answered | yes |  | correct |  | 1805 |
| dev-006 | easy | answered | yes |  | correct |  | 1578 |
| dev-007 | medium | answered | yes |  | correct |  | 2585 |
| dev-008 | medium | answered | yes |  | correct |  | 2263 |
| dev-009 | medium | answered | yes |  | correct |  | 1777 |
| dev-010 | medium | answered | yes |  | correct |  | 2424 |
| dev-011 | medium | answered | yes |  | correct |  | 1856 |
| dev-012 | medium | answered | yes |  | correct |  | 4108 |
| dev-013 | medium | answered | yes |  | correct |  | 2388 |
| dev-014 | easy | answered | yes |  | correct |  | 1785 |
| dev-015 | medium | answered | yes |  | correct |  | 3776 |
| dev-016 | medium | answered | yes |  | correct |  | 2806 |
| dev-017 | hard | answered | yes | yes | correct |  | 5558 |
| dev-018 | hard | answered | yes |  | correct |  | 1944 |
| dev-019 | medium | answered | yes |  | correct |  | 1848 |
| dev-020 | hard | answered | yes |  | correct |  | 3670 |
| dev-021 | hard | answered | yes |  | correct |  | 2896 |
| dev-022 | easy | answered | yes |  | correct |  | 1832 |
| dev-023 | medium | answered | yes |  | correct |  | 2376 |
| dev-024 | easy | answered | yes |  | correct |  | 2395 |
| dev-025 | medium | answered | yes |  | correct |  | 2043 |
| dev-026 | easy | answered | yes |  | correct |  | 2003 |
| dev-027 | hard | answered | yes |  | correct |  | 2036 |
| dev-028 | easy | answered | yes |  | correct |  | 84271 |
| dev-029 | hard | execution_failed | no |  | execution_error (triaged) | Local network outage during the run: the database connection dropped (QUERY_FAILED) at the same time as the Bedrock call | 1251276 |
| dev-030 | medium | generation_failed | no |  | generation_failure (triaged) | Network outage: Bedrock call failed with a connection error. Run replaced. | 502 |
| dev-031 | medium | generation_failed | no |  | generation_failure (triaged) | Network outage: Bedrock call failed with a connection error. Run replaced. | 1020 |
| dev-032 | medium | generation_failed | no |  | generation_failure (triaged) | Network outage: Bedrock call failed with a connection error. Run replaced. | 815 |
| dev-033 | hard | generation_failed | no |  | generation_failure (triaged) | Network outage: Bedrock call failed with a connection error. Run replaced. | 3258 |
| dev-034 | hard | generation_failed | no |  | generation_failure (triaged) | Network outage: Bedrock call failed with a connection error. Run replaced. | 1618823 |
| dev-035 | hard | generation_failed | no |  | generation_failure (triaged) | Network outage: Bedrock call failed with a connection error. Run replaced. | 1563 |

## Attempts that did not pass

| Item | Attempt | Outcome | Validation codes |
|---|---|---|---|
| dev-017 | generation | rejected | INVALID_JOIN_PATH |
| dev-030 | generation | model_error |  |
| dev-031 | generation | model_error |  |
| dev-032 | generation | model_error |  |
| dev-033 | generation | model_error |  |
| dev-034 | generation | model_error |  |
| dev-035 | generation | model_error |  |

Each attempt's SQL is in the JSON record.
