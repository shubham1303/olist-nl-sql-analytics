# 0008. Services deliberately excluded until a measured need exists

- Status: Accepted
- Date: 2026-09-23

## Context

It's easy to add AWS services and AI frameworks to a portfolio project for their name
value. Each one adds cost, failure modes and code to maintain.

## Decision

The following are **not** used unless a later, measured requirement justifies them in a
new ADR:

| Excluded | Why it isn't needed now |
|---|---|
| RAG / vector database | About 9 curated views plus metric definitions fit in the prompt |
| LangChain / agent frameworks | One structured model call plus at most one repair call |
| NAT Gateway | Lambda runs outside the VPC ([ADR 0001](0001-database-platform.md)) |
| RDS Proxy | The Data API handles connections |
| Cognito | A shared access code is enough for the demo ([ADR 0004](0004-public-access-and-cost-controls.md)) |
| WAF | Throttling, request limits and reserved concurrency cover the demo threat model |
| DynamoDB | No query history or cache in the MVP |
| SQS / Step Functions | The request path is synchronous and fits the time budget |
| X-Ray | Structured logs and EMF metrics answer the operational questions |
| LLM result summaries / LLM chart selection | [ADR 0003](0003-llm-provider-and-model.md), [ADR 0007](0007-deterministic-chart-selection.md) |

## Consequences

- There's less infrastructure to build, secure and pay for, and a clearer story about
  deliberate design.
- Revisiting any of these needs evidence, for example eval failures that trace to
  schema retrieval, or latency data.
