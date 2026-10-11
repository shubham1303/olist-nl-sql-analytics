# olist-nl-sql

Ask questions about the [Olist e-commerce dataset][olist] in plain English and get
back the answer as a table, along with the SQL that produced it and any assumptions
the model made along the way.

The interesting part of this project (for me anyway) isn't calling an LLM, it's
making it safe to run whatever SQL the LLM hands back. So most of the code is the
validator and the plumbing around it.

## How it works

1. The question goes to Claude Sonnet 5 on Bedrock, together with a system prompt
   generated from a catalog of the curated views (tables, columns, metric definitions).
2. The model has to reply by calling a `submit_answer` tool with the SQL, its
   interpretation of the question, and assumptions. The reply gets parsed strictly
   because Bedrock doesn't enforce the schema for this model.
3. The SQL goes through a sqlglot-based validator: single SELECT only, allowed views
   and columns only, no fan-out joins that would double count revenue, a row limit, etc.
   Details in [docs/sql-safety.md](docs/sql-safety.md).
4. If the validator rejects it for a fixable reason, the model gets exactly one more
   try with the error code.
5. The validator's regenerated SQL (never the model's original text) runs against
   Postgres as a read-only role that can only see the analytics views.

The model never sees actual rows from the database, and it's never called more
than twice per question.

## Where it's at

Phases 1-3 are done: local Postgres with the curated views, the validator, and the
pipeline + CLI. I'm still waiting on Bedrock model access, so right now the pipeline
runs end to end only with the fake model (`--fake-sql`). The live smoke test skips
itself until access comes through.

Phase 4 is in progress: the eval harness and 50 drafted questions (30 dev / 20 held
out) are in [eval/](eval/README.md). No accuracy numbers yet, because every reference
answer needs a human check first. After that comes a small React UI, then deploying to AWS (Lambda + Aurora
Serverless). The full roadmap is in [plan.md](plan.md), and the reasoning behind
most decisions is written up as ADRs in [docs/adr](docs/adr/README.md).

## Running it locally

You need [uv](https://docs.astral.sh/uv/), Docker, and Node 24 if you want to touch
the frontend.

```sh
cp .env.example .env          # set the db passwords
docker compose up -d --wait   # postgres 16 on 127.0.0.1:5432
cd backend
uv sync
uv run python -m olist_nlsql.dbsetup download   # pulls the kaggle zip, checks sha256
uv run python -m olist_nlsql.dbsetup build
```

Then ask something:

```sh
# real model (needs AWS creds + Bedrock access, see docs/local-development.md)
uv run python -m olist_nlsql ask "What was merchandise revenue in 2017?"

# offline, you supply the "model" SQL yourself
uv run python -m olist_nlsql ask "How many orders?" --fake-sql "SELECT COUNT(*) FROM orders"
```

`--json` gives the full result, `--show-prompt` prints what gets sent to the model.
AWS credentials come from your normal AWS profile/SSO, not from `.env`.

## Tests

```sh
uv run pytest                  # unit tests, no db or aws needed
uv run pytest -m integration   # needs the docker db
uv run pytest -m live -s       # hits bedrock for real, never runs in CI
uv run ruff check . && uv run mypy
```

## Repo layout

- `backend/` - the Python package (`olist_nlsql`): catalog, db setup, validator, llm client, pipeline, CLI
- `frontend/` - Vite + React scaffold, nothing real in it yet
- `infra/main/` - Terraform, only providers/variables so far
- `docs/` - design notes and ADRs

## Data

The Olist dataset is CC BY-NC-SA 4.0. It's downloaded by the setup script and
isn't committed here.

[olist]: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
