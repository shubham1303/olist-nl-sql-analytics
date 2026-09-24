# Olist NL-to-SQL Analytics — Implementation Plan

Status: **Phase 2 complete; Phase 3 not started.** Decisions locked in [docs/adr/](docs/adr/README.md).
Last updated: 2026-09-23

---

## 1. Goal

Non-technical users ask business questions in plain English about the Olist Brazilian
E-Commerce dataset. They get back a table, a chart picked automatically, the SQL that
produced it, and the metric definitions and assumptions used.

What makes it portfolio-worthy is **not** the LLM call. It is:

1. **Defence in depth for LLM-generated SQL.** The database role is the security
   boundary, and validation sits on top of it for user experience and early rejection.
2. **An honest, reproducible evaluation.** A verified benchmark with a held-out split
   and separately reported stage metrics.
3. **Lean, reproducible cloud infrastructure.** Terraform, least-privilege IAM, no VPC
   Lambda, no NAT, scale-to-zero, and observability that answers real questions.

---

## 2. Locked decisions (summary)

| Area | Decision | ADR |
|---|---|---|
| Database | Aurora Serverless v2 PG + RDS Data API (AWS); Docker Postgres + psycopg (local); `QueryExecutor` abstraction with shared contract tests; `aws_s3` bulk load; auto-pause + `/status` warm-up | [0001](docs/adr/0001-database-platform.md) |
| Security | DB role `analytics_reader` is the boundary (SELECT on `analytics` only, read-only, statement timeout); least-privilege IAM (one cluster, one secret); sqlglot is layer two with useful rejection messages | [0002](docs/adr/0002-database-is-the-security-boundary.md) |
| LLM | Bedrock `us-east-1`, Claude Sonnet 5 via `us.anthropic.claude-sonnet-5` (verified ACTIVE); model ID only in config; ≤ 2 model calls per question; results never sent back to the model | [0003](docs/adr/0003-llm-provider-and-model.md) |
| Access & cost | Shared access code (hash stored server-side); route throttling; 500-char question cap; 4 KiB body; reserved concurrency; bounded output; $20 budget at 50/80/100% (alert, not cap) | [0004](docs/adr/0004-public-access-and-cost-controls.md) |
| Schema | Curated `analytics` views over hidden `raw` schema; one `catalog.yaml` generates both prompt context and validator allowlist; geolocation excluded; catalog resolves known terms, otherwise state the assumption and answer | [0005](docs/adr/0005-curated-analytics-schema-and-catalog.md) |
| Evaluation | 50 questions: 30 dev / 20 held-out; human-verified references; no tuning on held-out; stage metrics reported separately; no fabricated numbers | [0006](docs/adr/0006-evaluation-methodology.md) |
| Charts | Deterministic frontend rules from result shape; no LLM | [0007](docs/adr/0007-deterministic-chart-selection.md) |
| Exclusions | No RAG/vector DB, LangChain/agents, NAT, RDS Proxy, Cognito, WAF, DynamoDB, SQS, X-Ray | [0008](docs/adr/0008-excluded-services.md) |
| Tooling | Python 3.13 + uv + ruff + mypy strict + pytest; Vite/React/TS + Vitest + npm; Terraform single root; GitHub Actions | [0009](docs/adr/0009-tooling-and-repo-conventions.md) |
| Revenue | Canonical revenue = merchandise revenue (item price, excl. freight, eligible orders); freight, total order value, payment value are separate metrics | [0010](docs/adr/0010-canonical-revenue.md) |
| Attribution | Latest review per order; order outcomes attributed fully to each seller/category; grouped outcome counts not additive | [0011](docs/adr/0011-review-and-outcome-attribution.md) |
| Categories | Raw values unchanged; corrections/manual translations only in curated layer with source, normalized value, provenance | [0012](docs/adr/0012-category-translation-provenance.md) |
| Time window | 2017-01..2018-08 recommended for trends/comparisons; never auto-filtered; requested periods preserved with caveat | [0013](docs/adr/0013-recommended-time-window.md) |
| SQL validation | sqlglot AST, fail-closed, catalog-driven allowlists; joins via relationship key domains; uniqueness-based cardinality; fan-out + bridge-attribution rules; regenerated SQL only | [0014](docs/adr/0014-sql-validation-design.md) |
| Model-visible set | Five fact views + product attributes; `customers`, `sellers` and product lifetime columns hidden | [0015](docs/adr/0015-model-visible-relations.md) |

---

## 3. Target architecture (MVP)

```
Browser (React/TS)  — user enters access code once (sessionStorage)
   │  GET  /status   X-Access-Code   → {db: "ready" | "resuming"}  (triggers resume)
   │  POST /query    X-Access-Code   {question}
   ▼
API Gateway HTTP API   route throttling, CORS, 30 s integration timeout
   ▼
Lambda (Python 3.13, zip, reserved concurrency)
   ├─ 1. auth: constant-time compare of sha256(code) with ACCESS_CODE_SHA256
   ├─ 2. request validation: JSON schema, ≤ 4 KiB, question 1–500 chars
   ├─ 3. prompt: generated from catalog.yaml (views, columns, metrics, aliases) + few-shots
   ├─ 4. Bedrock (config-driven model) → {sql, assumptions[], metrics_used[]}
   ├─ 5. sqlglot validation: one SELECT, allowlisted relations/columns/functions, LIMIT ≤ 1000
   ├─ 6. execute via RDS Data API as analytics_reader (statement_timeout 10 s)
   ├─ 7. on validation/execution error: ONE repair call with the error; then fail cleanly
   └─ 8. return {sql, assumptions, metrics_used, columns[{name,type}], rows, truncated, timings}
   ▼
Aurora Serverless v2 PostgreSQL (0–2 ACU, auto-pause), private subnets, S3 gateway endpoint
   schema raw (hidden) → schema analytics (curated views) ← role analytics_reader

CloudWatch: structured JSON log per request, EMF metrics, dashboard, alarms
AWS Budgets: $20/month, notifications at 50/80/100% + forecast
```

---

## 4. Repository structure

```
olist-nl-sql/
├── README.md
├── plan.md
├── .github/workflows/ci.yml
├── docs/
│   ├── adr/                    # decisions (0001–0015)
│   ├── architecture.md         # Phase 9
│   ├── sql-safety.md           # validator guarantees, grain analysis, limitations
│   ├── data-model.md           # raw → analytics design, grains, data-quality caveats
│   ├── metrics.md              # metric definitions and the revenue decision
│   └── local-database.md       # Docker Postgres commands, roles, build steps
├── data/raw/                   # downloaded CSVs — git-ignored (CC BY-NC-SA 4.0)
├── docker-compose.yml          # local Postgres 16, loopback only
├── .env.example                # credentials template (.env is git-ignored)
├── backend/
│   ├── pyproject.toml, uv.lock
│   ├── src/olist_nlsql/
│   │   ├── config.py           # the ONLY place defaults (incl. model ID) live
│   │   ├── service.py          # orchestration                          (Phase 3)
│   │   ├── catalog/            # catalog.yaml + strict loader (done); prompt rendering (Phase 3)
│   │   ├── dbsetup/            # dataset download/verify, build CLI, sql/010–040 (done)
│   │   ├── sqlsafety/          # validator, grain analysis, policy from catalog (done)
│   │   ├── db/                 # QueryExecutor protocol + PostgresExecutor (done); data_api (Phase 7)
│   │   ├── llm/                # protocol, bedrock, fake, prompts        (Phase 3)
│   │   ├── api/                # lambda_handler, local_app (dev only)     (Phase 6 / 7)
│   │   └── evaluation/         # runner, compare, report                 (Phase 4)
│   └── tests/unit | integration | live
├── eval/                       # Phase 4
│   ├── benchmark/dev.yaml      # 30 questions — used for tuning
│   ├── benchmark/test.yaml     # 20 questions — held-out, never tuned on
│   └── results/                # committed run reports (json + md), one per run
├── frontend/                   # Vite + React + TS
│   └── src/charts/selectChart.ts   # Phase 6
└── infra/
    └── main/                   # single Terraform root, files split by concern
```

---

## 5. Phases and milestones

A phase is done only when its milestone is met and CI is green.

| # | Phase | Deliverables | Milestone |
|---|---|---|---|
| 0 | **Scaffold** | ADRs; repo skeleton; backend project (uv, ruff, mypy, pytest, config module); Vite React TS app with Vitest; Terraform root skeleton; `ci.yml`; README | All local checks that CI runs pass: backend lint/format/types/tests, frontend lint/types/tests/build, `terraform fmt`/`validate` |
| 1 ✅ | **Data foundation (local)** | `docker-compose.yml`; pinned-checksum download; `raw` schema + load; 8 curated `analytics` views; `analytics_reader` role; initial `catalog.yaml` + drift test; `QueryExecutor` + `PostgresExecutor`; data-model / metrics / local-database docs; integration job in CI | **Met:** 168 integration tests pass from a clean volume; role tests prove no writes/DDL/raw access even with read-only disabled; revenue identical across all views and equal to an independent CSV recomputation; audit control totals reconcile exactly |
| 2 ✅ | **SQL safety + semantic validation** | Catalog relationships, visibility, function/cast allowlists; sqlglot validator with stable error codes; join-path + fan-out + attribution analysis; adversarial corpus; `sql-safety.md`; ADRs 0014–0015 | 100% of attack corpus rejected with a useful message; LIMIT always enforced; catalog drift test passes |
| 3 | **NL→SQL core** | `LlmClient` protocol + Bedrock client + fake; prompt built from catalog; service with ≤ 1 repair; CLI `ask "…"`; live smoke test | End-to-end answers locally for a handful of sample questions; unit tests cover happy / repair / give-up paths |
| 4 | **Evaluation harness** | 50 drafted items (30 dev / 20 test) → **human verification** of each reference SQL/result; runner; result comparator; failure categoriser; report generator | Baseline report committed with stage metrics for dev; one held-out checkpoint run recorded |
| 5 | **Accuracy iteration (dev only)** | Catalog, view, prompt and few-shot changes driven by dev failure categories; optional second model via config | Measured dev improvement with a changelog; one held-out checkpoint run recorded |
| 6 | **Local API + UI** | `local_app.py`; React UI: access code, question box, table, auto chart, SQL panel, metrics and assumptions, truncation, error and "Starting analytics database..." states | Full local demo against Docker Postgres + real Bedrock; component and chart-rule tests pass |
| 7 | **AWS deployment** | Terraform: state bucket, VPC (private subnets, S3 gateway endpoint), Aurora + Data API, secrets, `aws_s3` load, Lambda (+ reserved concurrency), HTTP API (+ throttling), logs/EMF/dashboard/alarms, $20 budget; `DataApiExecutor`; `/status` warm-up | Deployed API passes executor contract suite and an eval smoke subset; cold-start flow verified from a paused cluster |
| 8 | **Hosting + CD** | S3 + CloudFront (OAC); GitHub OIDC role; deploy workflow; manual eval workflow | Merge to main deploys; public URL works; no long-lived AWS keys |
| 9 | **Polish** | README with diagram, eval results (as measured), cost breakdown (as measured), security write-up, demo GIF | Someone unfamiliar can understand the project in 2 minutes and reproduce it in 30 |

**Stretch (after Phase 9, each needs justification):** follow-up questions, query cache,
EXPLAIN cost guard, Playwright e2e, feedback capture.

---

## 6. Major technical risks

| Risk | Mitigation |
|---|---|
| Wrong answers on business semantics | Curated views + metric catalog; dev-set iteration; held-out reporting |
| Validator false rejections / bypass | DB role is the boundary; allowlist validator; every verified reference query must pass |
| 30 s API timeout vs Bedrock + Aurora resume | `/status` warm-up flow; resume retry with backoff; ≤ 2 model calls; client timeouts |
| Cost abuse | Access code, throttling, reserved concurrency, input and output caps, budget alerts |
| Local vs Data API behaviour drift | Shared executor contract suite against both |
| Data API 1 MiB response cap | Row, column and text-length caps |
| Unverified benchmark references | Mandatory human verification fields; unverified items excluded from scoring |
| Lambda packaging from Windows | Build for the Lambda platform explicitly or in CI |
| **AWS CLI currently uses root credentials** | Before Phase 7: create an IAM Identity Center (or IAM) admin user, use a named profile, lock away root keys (delete root access keys if any exist) |
| Dataset licence (CC BY-NC-SA 4.0) | Download script; never commit raw data; attribution in README |

---

## 7. Local vs AWS

| Component | Local | AWS |
|---|---|---|
| Database | Docker Postgres (same major version, same SQL scripts) | Aurora Serverless v2 |
| DB access | `PostgresExecutor` (psycopg) as `analytics_reader` | `DataApiExecutor` (boto3) with the `analytics_reader` secret |
| LLM | Real Bedrock via a local AWS profile; fake client in tests | Bedrock via the Lambda role |
| API | `local_app.py` (dev dependency only) | `lambda_handler.py` behind HTTP API |
| Frontend | Vite dev server | S3 + CloudFront (Phase 8) |
| Eval | Primary environment | Smoke subset against the deployed API |
| Logs | Same JSON to stdout | CloudWatch Logs + EMF |

---

## 8. Testing strategy

| Component | How it's tested |
|---|---|
| Config | Unit: defaults, env overrides, invalid values rejected |
| DB role | Integration: `analytics_reader` can't write, run DDL, read `raw`, or escape read-only; the timeout fires |
| Catalog | Integration drift test (catalog ↔ live views); snapshot of the rendered prompt |
| Validator | Table-driven unit tests: attack corpus rejected with the expected codes; verified reference queries accepted; LIMIT injection and clamping |
| Executors | One contract suite, run against Docker Postgres and (with the `live` marker) the Data API |
| LLM client | Fake-client unit tests; malformed-output parsing; opt-in live smoke test |
| Service | Fake LLM + real local DB: happy, repair, give-up, and over-limit paths |
| Lambda handler | API Gateway v2 event fixtures: auth, limits, CORS, error shapes |
| Chart rules | Vitest fixtures per rule |
| UI | Vitest + React Testing Library: loading, resuming, error, empty, truncated states |
| Infra | `fmt`/`validate` in CI; `plan` review; post-deploy smoke script |
| NL→SQL quality | The eval harness ([ADR 0006](docs/adr/0006-evaluation-methodology.md)) |

---

## 9. Progress log

### Phase 2 (done, 2026-09-24)

- Catalog extended: `exposed` flags, grain keys, 7 relationships, bridge attribution keys, 42-function allowlist, cast types; relevant metrics derived per relation.
- Model-visible set: 5 fact views + product attributes (ADR 0015); `customers`, `sellers`, product lifetime columns hidden.
- `sqlsafety` validator: 8 fail-closed stages; executes only SQL regenerated from the validated AST and re-parsed.
- Grain analysis catches fan-out through joins, CTEs, derived tables and WHERE subqueries; accepts pre-aggregation, COUNT(DISTINCT), MIN/MAX, EXISTS.
- Corpus: 49 accepted + 132 rejected queries; 534 backend tests pass (291 unit, 243 integration).
- Found and fixed: sqlglot models `AND`/`OR`/`EXISTS` as functions; operator nodes could borrow a column's name for the allowlist; sqlglot regenerates `E'\'` as an unterminated string (now refused by the round-trip check).
- Executor contract suite for the Data API deferred to Phase 7 (only one executor exists).

### Phase 1 (done, 2026-09-23)

- Dataset pinned by per-file SHA-256; Kaggle archive hash matches the earlier independent audit.
- `dbsetup build` rebuilds everything in ~5 s; `dbsetup views` rebuilds the analytics layer only.
- 8 views: orders, order_items, order_sellers, order_categories, order_payments, customers, sellers, products (grains in [docs/data-model.md](docs/data-model.md)).
- 16 catalog metrics, every one executed and value-checked by tests ([docs/metrics.md](docs/metrics.md)).
- Canonical revenue = merchandise revenue: item price for non-canceled/unavailable orders with items (R$13,494,400.74).
- Found and fixed: `localhost` → IPv6 stall on Windows (use 127.0.0.1); `views` not dropping `analytics_internal`; PUBLIC could connect to the `postgres` database.
- CI green on GitHub for `f8609fd` (run 35932520382): backend, database (Kaggle download → build → 169 integration tests), frontend, infra — all passed on the first run.
- Phase 1 decisions recorded as ADRs 0010–0013 (merchandise revenue; latest review + full outcome attribution; translation provenance; recommended — not enforced — time window).

### Phase 0 checklist

- [x] ADRs 0001–0009
- [x] plan.md updated
- [x] `.gitignore`, `.gitattributes`, `.editorconfig`, `.nvmrc`, README
- [x] `backend/`: pyproject (uv, ruff, mypy strict, pytest markers), `olist_nlsql.config`, unit tests
- [x] `frontend/`: Vite React TS, oxlint, Vitest + RTL, smoke test
- [x] `infra/main/`: Terraform version and provider pins, variables, no resources yet
- [x] `.github/workflows/ci.yml`
- [x] All CI-equivalent checks pass locally from a clean install
- [ ] CI green on GitHub (needs a remote; first push is the user's call)
