# Eval run `20261013T073332Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-13T07:33:32+00:00 |
| Git commit | `115059eaf48202253881ceab993e44be48d571f5` (uncommitted changes) |
| Model | `us.anthropic.claude-sonnet-4-6` |
| Model settings | via_api=https://kfssnwtgya.execute-api.us-east-1.amazonaws.com |
| Prompt version | v2 |
| Benchmark hash | `bd2cae1f5670c6a6` |
| Items | 8 (8 verified and scored, 0 unverified and not scored) |

## Stage metrics (verified items)

| Stage | Count | Rate |
|---|---:|---:|
| SQL generated | 8/8 | 100.0% |
| Passed validation | 8/8 | 100.0% |
| Executed | 8/8 | 100.0% |
| **Correct result** | **8/8** | **100.0%** |

## Supporting metrics

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 2280.95 / 5638.54 ms
- Tokens per question (input incl. cached + output): 0.0; output only: 0.0; input served from cache: n/a
- Model calls per question: 1.0

| Difficulty | Correct |
|---|---:|
| easy | 2/2 |
| medium | 4/4 |
| hard | 2/2 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 8 |

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-002 | easy | answered | yes |  | correct |  | 2036 |
| dev-006 | easy | answered | yes |  | correct |  | 1709 |
| dev-007 | medium | answered | yes |  | correct |  | 2767 |
| dev-008 | medium | answered | yes |  | correct |  | 2260 |
| dev-012 | medium | answered | yes |  | correct |  | 4167 |
| dev-013 | medium | answered | yes |  | correct |  | 2281 |
| dev-021 | hard | answered | yes |  | correct |  | 3312 |
| dev-034 | hard | answered | yes |  | correct |  | 5639 |
