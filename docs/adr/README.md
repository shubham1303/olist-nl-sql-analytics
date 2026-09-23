# Architecture Decision Records

Short records of decisions that shape the system. Each ADR is immutable once
accepted; to change a decision, add a new ADR that supersedes it.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-database-platform.md) | Database platform: Aurora Serverless v2 + RDS Data API, Docker Postgres locally | Accepted |
| [0002](0002-database-is-the-security-boundary.md) | The database is the primary security boundary; sqlglot validation is layer two | Accepted |
| [0003](0003-llm-provider-and-model.md) | Bedrock in us-east-1, Claude Sonnet 5 via US inference profile, config-driven | Accepted |
| [0004](0004-public-access-and-cost-controls.md) | Shared access code, throttling, request limits, $20 budget | Accepted |
| [0005](0005-curated-analytics-schema-and-catalog.md) | Curated analytics views + one catalog as source of truth | Accepted |
| [0006](0006-evaluation-methodology.md) | 50-question benchmark, 30 dev / 20 held-out, verified references | Accepted |
| [0007](0007-deterministic-chart-selection.md) | Deterministic chart selection from result shape | Accepted |
| [0008](0008-excluded-services.md) | Services deliberately excluded until a measured need exists | Accepted |
| [0009](0009-tooling-and-repo-conventions.md) | Tooling and repository conventions | Accepted |

Template: [template.md](template.md)
