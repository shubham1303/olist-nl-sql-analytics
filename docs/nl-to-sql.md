# NL-to-SQL pipeline

The core of the application turns a business question into a validated, read-only
query and runs it. It's a fixed pipeline, not an agent. There is at most one repair,
and the model never sees data.

Code:
- [pipeline.py](../backend/src/olist_nlsql/pipeline.py): orchestration
- [llm/prompts.py](../backend/src/olist_nlsql/llm/prompts.py): all prompt text
- [llm/output.py](../backend/src/olist_nlsql/llm/output.py): the structured reply
- [llm/bedrock.py](../backend/src/olist_nlsql/llm/bedrock.py): Bedrock
- [cli.py](../backend/src/olist_nlsql/cli.py): the command line

Decisions:
- [ADR 0003](adr/0003-llm-provider-and-model.md): model and call limits
- [ADR 0016](adr/0016-bedrock-client-and-structured-output.md): endpoint, client and reply mechanism
- [ADR 0014](adr/0014-sql-validation-design.md): validator

## Flow

```mermaid
sequenceDiagram
    actor U as User / CLI
    participant P as Pipeline
    participant M as Bedrock bedrock-runtime (Claude Sonnet 5)
    participant V as SQL validator
    participant D as PostgreSQL (analytics_reader)
    U->>P: question
    P->>P: check length (≤ 500 chars); build catalog prompt
    P->>M: call 1: catalog prompt + question
    M-->>P: submit_answer tool call {can_answer, interpretation, sql, assumptions, metrics_used}
    P->>V: validate model SQL
    alt accepted
        V-->>P: regenerated SQL (schema-qualified, LIMIT applied)
    else rejected with a repairable code
        V-->>P: error code + details
        P->>M: call 2: catalog prompt + question + rejected SQL + code + compact fix
        M-->>P: submit_answer tool call
        P->>V: validate repaired SQL
        V-->>P: regenerated SQL, or rejection (final)
    end
    P->>D: execute the validator's SQL only
    D-->>P: typed columns + rows (≤ 1,000, truncation flag)
    P-->>U: structured result
```

## Rules the pipeline enforces

| Rule | How |
|---|---|
| At most **two** model calls per question | Call 1 generates. Call 2 runs only after a *repairable* validator rejection. There is no loop. |
| The model's SQL is **never executed** | Only `ValidationResult.sql` reaches the executor. That SQL is regenerated from the validated tree. |
| Every executed query passed the validator | See the previous rule. Tests re-validate every executed SQL. |
| Execution uses `analytics_reader` | The CLI and tests connect with the reader credentials only (`reader_conninfo()`). |
| The model **never receives database rows** | Nothing is sent after execution. There are no summaries and no third call. Review text in the data can't inject instructions. |
| Hidden relations stay hidden | The prompt is generated from the catalog's exposed relations and columns only. |
| No credentials in the repo | AWS credentials come from the standard AWS chain. `.env` holds database passwords only and is git-ignored. A test scans the repo. |
| The database is still the boundary | Even if validation were bypassed, `analytics_reader` can't write, change the schema or read `raw` (ADR 0002). |

A write attempt (`WRITE_OPERATION`) is **not** repaired, because a second try at
something the question should never have produced isn't useful. A validator bug
(`VALIDATOR_INTERNAL_ERROR`) isn't repaired either. Database failures (a timeout or an
execution error) aren't repaired, because the SQL was valid.

## The prompt

The system prompt is built deterministically from the catalog
(`PROMPT_VERSION = "v1"`). It's identical on both calls, so it's marked for prompt
caching. It has eight sections:

| Section | Contents | Size |
|---|---|---:|
| Intro | Task, currency, "validated, read-only" | 0.3k chars |
| SQL rules | One SELECT, listed relations and columns only, no `SELECT *`, listed joins only, fan-out rule, bridge attribution rule, the function and cast allowlists from the catalog, no `NOW()`, row cap | 1.7k |
| Business rules | Merchandise revenue, `customer_unique_id`, late-rate denominator, latest review, catalog definitions over assumptions, stating assumptions, keeping the requested period, `can_answer = false` | 1.2k |
| Dataset | Catalog notes (date coverage, recommended window) and glossary | 1.2k |
| Relations | Each exposed relation: grain, key, description, columns with types, descriptions and allowed values, caveats | 11.8k |
| Relationships | The 7 allowed joins with their keys | 0.7k |
| Metrics | 16 metrics: name, aliases, definition, SQL, exclusions, caveats | 5.8k |
| Output | Call `submit_answer` once, and its fields | 0.3k |
| **Total** | | **≈ 22.9k chars, ≈ 5.7k tokens** (chars / 4) |

`python -m olist_nlsql prompt --stats` prints the current sizes. A unit test fails if
the prompt passes 30,000 characters, so growth gets noticed.

The model is told that its SQL will be validated, and it is told the rules. It isn't
told how the validator works internally.

## Structured reply

The request goes to Bedrock's **bedrock-runtime** endpoint (InvokeModel with the
Anthropic Messages body, via `anthropic.AnthropicBedrock`). The model ID is
`us.anthropic.claude-sonnet-5`.

JSON-schema structured outputs (`output_config.format`) aren't supported for Claude
Sonnet 5 on Bedrock. Instead the model answers through **one tool call**,
`submit_answer`, whose `input_schema` is the schema below:
- With thinking disabled (the default), the call is forced with `tool_choice`.
- With adaptive thinking, the prompt asks for the call. A reply without it is a
  generation failure.

Bedrock doesn't enforce the schema for this model, so `parse_generation` is the real
check:

```json
{
  "can_answer": true,
  "interpretation": "Total merchandise revenue for orders placed in 2017.",
  "sql": "SELECT SUM(revenue) AS revenue FROM analytics.orders WHERE ...",
  "assumptions": [],
  "metrics_used": ["revenue"]
}
```

- Keys must match the schema exactly, and each value must have the right type.
- `sql` must be non-empty when `can_answer` is true, and is ignored when it's false.
- There is no chart field, and the model is never asked to describe results.
- A reply that fails parsing, or doesn't call the tool, is a **generation failure**. It
  isn't repaired, because it means something is wrong with the call, not with the SQL.
  The benchmark will show how often this happens.

## Repair

The repair call reuses the cached system prompt and sends a short user message:

```text
Question: Revenue by category?

Your previous SQL was rejected by the validator:
SELECT i.product_category, SUM(o.revenue) FROM orders o JOIN order_items i ON ...

Error: FANOUT_RISK
Fix: A join repeats rows before aggregation. Compute the value from its own relation,
aggregate the many side to one row per key in a subquery before joining, or use
COUNT(DISTINCT key). (aggregate=SUM(o.revenue), column=o.revenue, relation=orders)

Call submit_answer again with the corrected answer.
```

- The fix text is a fixed instruction for each error code, plus the validator's
  structured details. The validator's long human-readable message isn't sent.
- Bridge-attribution fan-out gets its own instruction ("group by
  seller_id / product_category").
- The result records which call produced the final SQL: `answer_source` is
  `generation` or `repair`, and `attempts` lists each call's outcome and validator
  codes.

## Result

`PipelineResult` is returned by the pipeline and printed by the CLI.
`to_dict()` gives a JSON-safe view, with decimals as strings and dates in ISO format.

| Field | Meaning |
|---|---|
| `status` | `answered`, `unanswerable`, `invalid_question`, `generation_failed`, `rejected`, `validator_error`, `execution_failed` |
| `interpretation`, `assumptions`, `metrics_used` | From the model's final reply |
| `generated_sql` | The model's final SQL as written (never executed) |
| `validated_sql` | The SQL that was executed |
| `repair_attempted`, `answer_source` | Whether a repair call happened, and which call answered |
| `columns`, `rows`, `row_count`, `truncated` | Typed columns and at most 1,000 rows |
| `warnings` | Validator warnings, for example row-level fan-out repetition |
| `timings` | `prompt_build_ms`, `model_generation_ms`, `repair_generation_ms`, `validation_ms`, `execution_ms`, `total_ms` |
| `attempts` | For each call: outcome, validator codes, model and validation time, tokens |
| `model_id`, `prompt_version` | For comparing evaluation runs |
| `error` | `stage`, `code`, `message`. Safe to show: no stack traces or credentials. |

### Failure modes

| Status | Stage / code | Cause |
|---|---|---|
| `invalid_question` | `input` / `EMPTY_QUESTION`, `QUESTION_TOO_LONG` | Rejected before any model call |
| `generation_failed` | `generation` / `access_denied`, `throttled`, `timeout`, `refused`, `truncated`, ... | The Bedrock call failed |
| `generation_failed` | `parsing` / `OUTPUT_PARSE_ERROR` | The reply didn't match the schema |
| `unanswerable` | none | The model said the catalog can't answer the question (e.g. product names) |
| `rejected` | `validation` / validator code | Still invalid after the repair, or not repairable (a write) |
| `validator_error` | `validator_internal` / `VALIDATOR_INTERNAL_ERROR` | A validator bug. Logged with its traceback at ERROR level. Never shown as a user mistake. |
| `execution_failed` | `execution` / `QUERY_TIMEOUT`, `QUERY_FAILED` | The database timed out (10 s role limit) or rejected validated SQL |

Every run logs one JSON line (`event: nlsql_pipeline`) to the `olist_nlsql.pipeline`
logger. It has the same fields as the result, minus rows and columns, and is enough
for later evaluation without a telemetry system.

## CLI

```sh
cd backend
uv run python -m olist_nlsql ask "What was merchandise revenue in 2017?"
uv run python -m olist_nlsql ask "Top 5 categories by revenue" --json
uv run python -m olist_nlsql ask "..." --show-prompt           # print the model request first
uv run python -m olist_nlsql prompt --stats                    # prompt section sizes

# Offline, no Bedrock: script the model's SQL (repeat --fake-sql to script a repair)
uv run python -m olist_nlsql ask "Revenue by category" \
  --fake-sql "SELECT i.product_category, SUM(o.revenue) FROM orders o JOIN order_items i ON o.order_id = i.order_id GROUP BY 1" \
  --fake-sql "SELECT product_category, SUM(revenue) AS revenue FROM order_items GROUP BY product_category"
```

Local setup, including AWS authentication, is in
[local-development.md](local-development.md).

## Smoke-test notes (Phase 3)

| Date | Result |
|---|---|
| 2026-09-24 | **Not run.** Bedrock refused every call: *"anthropic.claude-sonnet-5 is not available for this account"* (`agreementAvailability: NOT_AVAILABLE` for all Anthropic models). `pytest -m live` skips cleanly with that reason. Rerun after model access is granted. |

The 5 smoke questions are in
[test_bedrock_smoke.py](../backend/tests/live/test_bedrock_smoke.py). They check the
plumbing only and **are not an accuracy measurement**.

## Local timings (indicative, not benchmarks)

Measured on the development laptop against Docker PostgreSQL:

| Step | Typical |
|---|---:|
| Prompt build (after a one-time catalog load of about 50 ms) | < 0.1 ms |
| Validation (49 accepted corpus queries) | median 2.8 ms, 95th percentile 12 ms |
| Execution (6 representative queries) | 90–380 ms |
| Model call | not measured (no Bedrock access yet) |

## Limitations

- **No live model output yet**, so there's no evidence about how the prompt performs,
  which validator errors the model triggers, or how often repair works.
- The pipeline is single-turn with no clarification step (ADR 0005). Ambiguity is
  handled through stated assumptions.
- `metrics_used` is the model's own claim and isn't cross-checked against the SQL.
- The 60 s model timeout times two calls exceeds the API Gateway 30 s budget, so
  Phase 7 must tighten timeouts or effort.
- The prompt is English and tuned to this catalog. There's no retrieval, which isn't
  needed at about 6k tokens.
