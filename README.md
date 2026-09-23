# Olist NL-to-SQL Analytics

Ask business questions about the [Olist Brazilian E-Commerce dataset][olist] in plain
English and get back a table, an automatically selected chart, the SQL that produced
it, and the metric definitions and assumptions used.

> **Status:** Phase 0 (scaffold). See [plan.md](plan.md) for the roadmap and
> [docs/adr/](docs/adr/README.md) for the architecture decisions.

## Architecture (target)

React/TypeScript frontend → API Gateway HTTP API → Python Lambda → Amazon Bedrock
(Claude Sonnet 5, config-driven) for SQL generation → sqlglot safety validation → Aurora
Serverless v2 PostgreSQL via the RDS Data API, as a read-only role that can see only
curated analytics views. Infrastructure is Terraform. Accuracy is measured on a
verified 50-question benchmark with a 20-question held-out split.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Python 3.13 package `olist_nlsql` (uv, ruff, mypy, pytest) |
| `frontend/` | Vite + React + TypeScript (oxlint, Vitest) |
| `infra/main/` | Terraform root configuration |
| `docs/adr/` | Architecture Decision Records |
| `.github/workflows/` | CI |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 automatically)
- Node.js 24 LTS (see `.nvmrc`)
- Terraform ≥ 1.10
- Docker (from Phase 1)

## Common commands

Backend (`cd backend`):

```sh
uv sync                    # create .venv and install dependencies
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # type check (strict)
uv run pytest              # unit tests (excludes integration and live)
uv run pytest -m integration   # needs Docker Postgres (Phase 1+)
```

Frontend (`cd frontend`):

```sh
npm ci
npm run dev                # local dev server
npm run lint
npm run typecheck
npm test
npm run build
```

Infrastructure (`cd infra/main`):

```sh
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

## Data licence

The Olist dataset is published under CC BY-NC-SA 4.0. Raw data is downloaded by
script and never committed to this repository.

[olist]: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
