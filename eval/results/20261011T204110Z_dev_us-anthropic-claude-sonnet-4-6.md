# Eval run `20261011T204110Z_dev_us-anthropic-claude-sonnet-4-6`

| | |
|---|---|
| Split | dev |
| Started | 2026-10-11T20:41:10+00:00 |
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
| **Correct result** | **28/30** | **93.3%** |

## Supporting metrics

- Repair rate: 0.0%; repairs that ended correct: n/a
- Latency p50 / p95: 1870.63 / 3180.39 ms
- Tokens per question (input incl. cached + output): 6979.5; output only: 214.2; input served from cache: 93.6%
- Model calls per question: 1.0

| Difficulty | Correct |
|---|---:|
| easy | 10/11 |
| medium | 12/13 |
| hard | 6/6 |

## Failure categories (verified items)

| Category | Items |
|---|---:|
| correct | 28 |
| untriaged_mismatch | 2 |

Automatic guesses still to triage: dev-005, dev-013 (`eval/triage/20261011T204110Z_dev_us-anthropic-claude-sonnet-4-6.yaml`).

## Items

| Item | Difficulty | Status | Correct | Repair | Category | Note | ms |
|---|---|---|---|---|---|---|---:|
| dev-001 | easy | answered | yes |  | correct |  | 1843 |
| dev-002 | easy | answered | yes |  | correct |  | 1735 |
| dev-003 | easy | answered | yes |  | correct |  | 1534 |
| dev-004 | easy | answered | yes |  | correct |  | 1553 |
| dev-005 | easy | answered | no |  | untriaged_mismatch | no generated column matches reference column 'average_review_score' | 1592 |
| dev-006 | easy | answered | yes |  | correct |  | 1592 |
| dev-007 | medium | answered | yes |  | correct |  | 2378 |
| dev-008 | medium | answered | yes |  | correct |  | 2125 |
| dev-009 | medium | answered | yes |  | correct |  | 1764 |
| dev-010 | medium | answered | yes |  | correct |  | 2950 |
| dev-011 | medium | answered | yes |  | correct |  | 1835 |
| dev-012 | medium | answered | yes |  | correct |  | 3180 |
| dev-013 | medium | answered | no |  | untriaged_mismatch | no generated column matches reference column 'average_review_score' | 1982 |
| dev-014 | easy | answered | yes |  | correct |  | 1610 |
| dev-015 | medium | answered | yes |  | correct |  | 2977 |
| dev-016 | medium | answered | yes |  | correct |  | 2912 |
| dev-017 | hard | answered | yes |  | correct |  | 3098 |
| dev-018 | hard | answered | yes |  | correct |  | 1764 |
| dev-019 | medium | answered | yes |  | correct |  | 1641 |
| dev-020 | hard | answered | yes |  | correct |  | 3613 |
| dev-021 | hard | answered | yes |  | correct |  | 2842 |
| dev-022 | easy | answered | yes |  | correct |  | 1871 |
| dev-023 | medium | answered | yes |  | correct |  | 2217 |
| dev-024 | easy | answered | yes |  | correct |  | 2023 |
| dev-025 | medium | answered | yes |  | correct |  | 1711 |
| dev-026 | easy | answered | yes |  | correct |  | 1979 |
| dev-027 | hard | answered | yes |  | correct |  | 1961 |
| dev-028 | easy | answered | yes |  | correct |  | 1555 |
| dev-029 | hard | answered | yes |  | correct |  | 2594 |
| dev-030 | medium | answered | yes |  | correct |  | 1596 |
