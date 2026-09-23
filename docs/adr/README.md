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
| [0010](0010-canonical-revenue.md) | Canonical revenue is merchandise revenue | Accepted |
| [0011](0011-review-and-outcome-attribution.md) | Latest review per order; full outcome attribution in seller/category views | Accepted |
| [0012](0012-category-translation-provenance.md) | Category translations: raw unchanged, corrections in the curated layer with provenance | Accepted |
| [0013](0013-recommended-time-window.md) | 2017-01 to 2018-08 is a recommended window, not an automatic filter | Accepted |

Template: [template.md](template.md)
