# 0003. Bedrock in us-east-1, Claude Sonnet 5 via US inference profile, config-driven

- Status: Accepted
- Date: 2026-09-23

## Context

We need natural-language-to-SQL generation on AWS. Models change quickly. The
application should be evaluated across models on the same benchmark rather than
designed around one model.

## Decision

- **Region:** `us-east-1`.
- **Initial model:** Claude Sonnet 5 on Amazon Bedrock via the US cross-region
  inference profile `us.anthropic.claude-sonnet-5`. This profile was verified ACTIVE in
  the target account on 2026-09-23 with `aws bedrock list-inference-profiles`.
- **Configuration-driven:** the model/profile ID, maximum output tokens and any
  reasoning/effort settings come from configuration (environment variables locally,
  Terraform variables in AWS). Application logic never references a model ID literal.
  The only place the default appears is the config module.
- **Interface:** the service depends on an `LlmClient` protocol that returns a
  structured result `{sql, assumptions[], metrics_used[]}`. We will choose the concrete
  client (boto3 `bedrock-runtime` Converse, or the Anthropic SDK's Bedrock client) in
  Phase 3. The protocol makes that choice swappable. A deterministic fake client backs
  unit tests.
- **Bounded calls:** at most **two** model calls per question, one generation plus at
  most one repair after a validation or execution error. Output tokens are capped.
- **No result text to the model:** query results are never sent back to the LLM, so
  there are no LLM-written summaries. This removes a prompt-injection path (review text
  is user-generated) and saves tokens.

## Consequences

- Swapping or comparing models is a configuration change plus an eval run.
- Reasoning/effort settings affect latency (30 s API budget) and cost. We'll pick them
  from measured eval results, not assumptions.
- Model access and quotas are per account and region. Phase 3 begins with a live smoke
  test.
