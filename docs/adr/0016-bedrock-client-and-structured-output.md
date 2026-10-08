# 0016. Bedrock: bedrock-runtime endpoint, Messages request shape, forced tool call for structured replies

- Status: Accepted (live verification pending Bedrock model access)
- Date: 2026-09-24
- Refines [ADR 0003](0003-llm-provider-and-model.md): same region, model family, model
  ID and call limits. This ADR fixes the endpoint, the client and the reply mechanism.

## Context

Claude Sonnet 5 is reachable on two Bedrock endpoints, according to the
[AWS model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5.html)
and the [Messages API guide](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-messages-api.html)
(checked 2026-09-24):

| | `bedrock-runtime` | `bedrock-mantle` |
|---|---|---|
| Base URL | `https://bedrock-runtime.us-east-1.amazonaws.com` | `https://bedrock-mantle.us-east-1.api.aws/anthropic/v1/messages` |
| APIs for Sonnet 5 | Messages (as InvokeModel body, or the `/anthropic` route), Invoke, Converse | Messages only |
| Sonnet 5 model ID | Geo `us.anthropic.claude-sonnet-5` (also `eu.`, `au.`) or `global.anthropic.claude-sonnet-5`. The bare ID isn't supported for on-demand use. | `anthropic.claude-sonnet-5` (single-region, in-region) |
| Auth | SigV4 (IAM), or Bedrock API keys / bearer tokens | SigV4, or Bedrock API keys |
| Extras | Invocation logging, Guardrails, Knowledge Bases, etc. | Workspaces, `count_tokens` |
| AWS guidance | **Recommended for new applications** | Use for its specific features |
| Anthropic SDK class | `anthropic.AnthropicBedrock` (InvokeModel with the Messages body) | `anthropic.AnthropicBedrockMantle` |

**Structured outputs** (`output_config.format`) are **not** supported for Claude
Sonnet 5 on either endpoint. AWS lists structured outputs only for Sonnet 4.5,
Haiku 4.5, Opus 4.5 and Opus 4.6 on `bedrock-runtime`, and Mantle rejects
`output_config.format` with a 400.

### Correction of the first draft of this ADR

The first draft used `AnthropicBedrockMantle`, `anthropic.claude-sonnet-5` and
`output_config.format`. That combination was chosen deliberately, but from an
Anthropic-SDK-centric guide that describes `AnthropicBedrock` as a legacy path. It
wasn't checked against AWS's endpoint guidance or the Sonnet 5 feature matrix.
- The draft's claim that `us.` IDs "belong to InvokeModel/Converse" was wrong. A Mantle
  404 only shows that Mantle doesn't accept `us.` IDs.
- The structured-output mechanism would have returned 400 on the first live call. No
  test caught this, because Bedrock access was blocked.

## Decision

- **Endpoint:** `bedrock-runtime` in `us-east-1`, following AWS's recommendation. It
  suits the Phase 7 Lambda: IAM role (SigV4), invocation logging, CloudWatch.
  Nothing here needs Mantle-only features.
- **Client:** `anthropic.AnthropicBedrock(aws_region=...)`. It sends the Anthropic
  Messages body to `POST /model/{model-id}/invoke`, adds
  `anthropic_version: bedrock-2023-05-31`, and signs with SigV4 from the standard AWS
  credential chain. No credentials are stored or configured by the application.
- **Model ID:** `us.anthropic.claude-sonnet-5` (US geo inference profile, kept within
  US and Canada regions). This is the default for `NLSQL_BEDROCK_MODEL_ID`. `config.py`
  is the only place the default appears. `global.anthropic.claude-sonnet-5` is a
  configuration change away if data residency is relaxed.
- **Reply structure:** one tool, `submit_answer`, whose `input_schema` is the output
  schema (`can_answer`, `interpretation`, `sql`, `assumptions`, `metrics_used`).
  - With `NLSQL_LLM_THINKING=disabled` (the default) the call is **forced**
    (`tool_choice: {"type": "tool"}`). On Bedrock, Sonnet 5 accepts a forced tool call
    only with thinking disabled.
  - With `adaptive`, `tool_choice` is `auto` and the prompt asks for the call. A reply
    without the call is a generation failure.
  - The tool input is **not** schema-enforced by Bedrock. The application's strict
    parser is the check.
- **Effort:** `output_config.effort`, `medium` by default (`NLSQL_LLM_EFFORT`), with no
  sampling parameters. The benchmark will tune effort and thinking.
- **Caching:** an explicit `cache_control` breakpoint on the system prompt, supported
  for Sonnet 5 on `bedrock-runtime` (minimum 1,024 tokens; the prompt is about 5.7k).
- **Transport:** one SDK retry, a 60 s timeout, and SDK errors mapped to a stable
  `ModelError.kind`.

## Consequences

- Swapping models or profiles (`us.` or `global.`) is a configuration change. Swapping
  the transport would only replace `llm/bedrock.py` behind the `ModelClient` interface.
- Thinking is off by default. If the benchmark shows quality gains from adaptive
  thinking, the `auto` tool-choice path is ready, at the cost of a small risk of
  missing tool calls.
- **Phase 7 IAM:** the Lambda role needs `bedrock:InvokeModel` on the
  `us.anthropic.claude-sonnet-5` inference-profile ARN and on the foundation-model ARNs
  in the regions that profile routes to. The exact policy will be written from AWS's
  inference-profile documentation, not assumed.
- **Documentation inconsistency:** one AWS example calls `invoke_model` with the bare
  `anthropic.claude-sonnet-5` ID on `bedrock-runtime`, while the Sonnet 5 model card
  says the bare ID isn't supported there. We follow the model card.
- Verified 2026-09-24: `bedrock-runtime` accepts `us.anthropic.claude-sonnet-5` and
  resolves it to `anthropic.claude-sonnet-5`. The call is then refused only for model
  access (`agreementAvailability: NOT_AVAILABLE`). Request shape, tool use and parsing
  are covered by unit tests, but not yet by a live call.
