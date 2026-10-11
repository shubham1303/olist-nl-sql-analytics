# 0019. Claude Sonnet 4.6 is the current model; Sonnet 5 is a later config swap

- Status: Accepted
- Date: 2026-10-11
- Amends [ADR 0003](0003-llm-provider-and-model.md) (initial model) and
  [ADR 0016](0016-bedrock-client-and-structured-output.md) (model ID and the reason
  for the forced tool call). Endpoint, client, call limits, caching and the
  configuration-only model ID are unchanged.

## Context

ADRs 0003 and 0016 chose Claude Sonnet 5 through `us.anthropic.claude-sonnet-5`. That
inference profile was listed as ACTIVE, but every call has been refused: *"not
available for this account… contact AWS Sales"*. A use-case form went in on
2026-10-08 and the Support case is still open.

Every published number comes from `us.anthropic.claude-sonnet-4-6`, set through
`NLSQL_BEDROCK_MODEL_ID` with no code change:
- the Phase 4 and Phase 5 dev runs (latest 34/34),
- both held-out checkpoints (19/20, then 20/23),
- the live smoke test (5/5).

The ADRs still name a model that has never answered a question here.

AWS's Sonnet 4.6 model card (checked 2026-10-11) gives:
- **Access:** `bedrock-runtime` only, through InvokeModel and Converse. The US geo
  profile `us.anthropic.claude-sonnet-4-6` routes from us-east-1 to us-east-1,
  us-east-2 and us-west-2; a `global.` profile also exists.
- **Structured outputs:** supported (`output_config.format` and strict tool use).
- **Prompt caching:** explicit, with at least 1,024 tokens per checkpoint.

## Decision

- **Current model:** Claude Sonnet 4.6 via the US geo inference profile
  `us.anthropic.claude-sonnet-4-6`. It becomes the default of `NLSQL_BEDROCK_MODEL_ID`
  in `config.py`, still the only place a model ID appears.
- **Request shape unchanged.** It is still bedrock-runtime, `AnthropicBedrock`, and a
  forced `submit_answer` tool call with thinking disabled, effort `medium` and an
  explicit cache breakpoint. The reasons change:
  - The forced call is no longer needed for lack of structured outputs; Sonnet 4.6 has
    them. It stays because it works on both models. Sonnet 5 on Bedrock still has no
    structured outputs, so the swap back needs no code change.
  - It has also been measured. The model returned SQL on 100% of items in every
    Sonnet 4.6 run, and the strict parser remains the check.
  - The thinking rule still holds. A forced `tool_choice` is accepted only with thinking
    disabled; with thinking on, only `auto` or `none` work. That is a general rule for
    Claude on the Messages API, not something specific to Sonnet 5. The `adaptive`
    thinking path (`tool_choice: auto`) is unchanged.
  - Caching works on 4.6: runs read about 90% of input tokens from cache.
- **Not adopted now:** strict tool use (`"strict": true` on `submit_answer`). Sonnet 4.6
  supports it and it would enforce the schema. But the Sonnet 5 swap would have to
  remove it, so the request shape would depend on the model. Early runs did send
  `assumptions`/`metrics_used` as strings, which the parser now tolerates. Revisit if
  parse failures show up in dev runs.
- **Sonnet 5 later:** once AWS grants access, switching is a configuration change,
  `NLSQL_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-5`, plus:
  1. a live smoke test,
  2. a fresh dev run, ideally repeated, to set a Sonnet 5 baseline,
  3. a held-out checkpoint, recorded like any other.

  Results from the two models are reported separately, never mixed. Making Sonnet 5 the
  default needs a new ADR that cites those runs.

## Consequences

- The decision record now matches the published numbers, and the app works with no
  model environment variable set.
- **Phase 7 IAM:** the Lambda role needs `bedrock:InvokeModel` on the
  `us.anthropic.claude-sonnet-4-6` inference-profile ARN and on the foundation-model
  ARNs in its destination regions (us-east-1, us-east-2, us-west-2). A Sonnet 5 swap
  changes that policy too, so the model ID also feeds the Terraform variable.
- Docs that name Sonnet 5 as the running model are updated: `local-development.md`,
  `nl-to-sql.md`, README and code comments. The ADR 0016 correction story stays as
  history.
- If Sonnet 4.6 is retired first (AWS lists end of life no sooner than 2027-02-17), the
  same swap procedure applies.
