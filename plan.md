# Olist NL-to-SQL Analytics — Implementation Plan

Status: **Phases 0–9 done.** Live at https://dunn64bzakzr8.cloudfront.net (access code required); every merge to `main` deploys. On `us.anthropic.claude-sonnet-4-6`, prompt v3: dev 35/35 (3 runs), held-out 21/23 (original 20 items 19/20, human-written 2/3). Measured idle cost about $1.25/month. Decisions locked in [docs/adr/](docs/adr/README.md).
Last updated: 2026-10-14

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
| LLM | Bedrock `us-east-1`, Claude Sonnet 4.6 via `us.anthropic.claude-sonnet-4-6` (Sonnet 5 unavailable to the account; later config swap + re-baseline); model ID only in config; ≤ 2 model calls per question; results never sent back to the model | [0003](docs/adr/0003-llm-provider-and-model.md), [0019](docs/adr/0019-sonnet-4-6-current-model.md) |
| Access & cost | Shared access code (hash stored server-side); route throttling; 500-char question cap; 4 KiB body; reserved concurrency; bounded output; $20 budget at 50/80/100% (alert, not cap) | [0004](docs/adr/0004-public-access-and-cost-controls.md) |
| Schema | Curated `analytics` views over hidden `raw` schema; one `catalog.yaml` generates both prompt context and validator allowlist; geolocation excluded; catalog resolves known terms, otherwise state the assumption and answer | [0005](docs/adr/0005-curated-analytics-schema-and-catalog.md) |
| Evaluation | 57 questions: 34 dev / 23 held-out (7 human-written); human-verified references; no tuning on held-out; stage metrics reported separately; no fabricated numbers | [0006](docs/adr/0006-evaluation-methodology.md), [0018](docs/adr/0018-human-written-benchmark-items.md) |
| Charts | Deterministic frontend rules from result shape; no LLM | [0007](docs/adr/0007-deterministic-chart-selection.md) |
| Exclusions | No RAG/vector DB, LangChain/agents, NAT, RDS Proxy, Cognito, WAF, DynamoDB, SQS, X-Ray | [0008](docs/adr/0008-excluded-services.md) |
| Tooling | Python 3.13 + uv + ruff + mypy strict + pytest; Vite/React/TS + Vitest + npm; Terraform single root; GitHub Actions | [0009](docs/adr/0009-tooling-and-repo-conventions.md) |
| Revenue | Canonical revenue = merchandise revenue (item price, excl. freight, eligible orders); freight, total order value, payment value are separate metrics | [0010](docs/adr/0010-canonical-revenue.md) |
| Attribution | Latest review per order; order outcomes attributed fully to each seller/category; grouped outcome counts not additive | [0011](docs/adr/0011-review-and-outcome-attribution.md) |
| Categories | Raw values unchanged; corrections/manual translations only in curated layer with source, normalized value, provenance | [0012](docs/adr/0012-category-translation-provenance.md) |
| Time window | 2017-01..2018-08 recommended for trends/comparisons; never auto-filtered; requested periods preserved with caveat | [0013](docs/adr/0013-recommended-time-window.md) |
| SQL validation | sqlglot AST, fail-closed, catalog-driven allowlists; joins via relationship key domains; uniqueness-based cardinality; fan-out + bridge-attribution rules; regenerated SQL only | [0014](docs/adr/0014-sql-validation-design.md) |
| Model-visible set | Five fact views + product attributes; `customers`, `sellers` and product lifetime columns hidden | [0015](docs/adr/0015-model-visible-relations.md) |
| Bedrock client | `bedrock-runtime` endpoint via `anthropic.AnthropicBedrock` (InvokeModel, Messages body), forced `submit_answer` tool call with thinking disabled (works on 4.6 and on Sonnet 5, which lacks structured outputs on Bedrock), cached catalog prompt | [0016](docs/adr/0016-bedrock-client-and-structured-output.md), [0019](docs/adr/0019-sonnet-4-6-current-model.md) |

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
   ├─ 3. prompt: generated from catalog.yaml (views, columns, metrics, aliases); few-shots optional, none so far
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
├── .github/workflows/         # ci.yml; deploy.yml (after CI on main, OIDC); eval.yml (manual)
├── docs/
│   ├── adr/                    # decisions (0001–0019)
│   ├── architecture.md         # Phase 9
│   ├── sql-safety.md           # validator guarantees, grain analysis, limitations
│   ├── nl-to-sql.md            # pipeline flow, prompt, repair, result, failure modes
│   ├── local-development.md    # setup, AWS auth for Bedrock, tests
│   ├── data-model.md           # raw → analytics design, grains, data-quality caveats
│   ├── metrics.md              # metric definitions and the revenue decision
│   ├── local-database.md       # Docker Postgres commands, roles, build steps
│   ├── deployment.md           # AWS deploy, hosting, CD, cost, cold starts
│   └── spikes/                 # measured experiments (Aurora resume)
├── data/raw/                   # downloaded CSVs — git-ignored (CC BY-NC-SA 4.0)
├── docker-compose.yml          # local Postgres 16, loopback only
├── .env.example                # credentials template (.env is git-ignored)
├── backend/
│   ├── pyproject.toml, uv.lock
│   ├── src/olist_nlsql/
│   │   ├── config.py           # the ONLY place defaults (incl. model ID) live
│   │   ├── pipeline.py         # orchestration: prompt → model → validator → repair → DB (done)
│   │   ├── cli.py              # python -m olist_nlsql ask/prompt (done)
│   │   ├── catalog/            # catalog.yaml + strict loader (done)
│   │   ├── dbsetup/            # dataset download/verify, local build, aws-build via Data API (done)
│   │   ├── sqlsafety/          # validator, grain analysis, policy from catalog (done)
│   │   ├── db/                 # QueryExecutor protocol, PostgresExecutor, DataApiExecutor (done)
│   │   ├── llm/                # client protocol, bedrock, fake, prompts, output schema (done)
│   │   ├── api/                # handlers, local_app, lambda_handler, EMF metrics (done)
│   │   └── evaluation/         # benchmark, runner, compare, report, CLI (done)
│   ├── scripts/build_lambda.py # reproducible arm64 Lambda zip
│   └── tests/unit | integration | live (+ executor_contract.py shared by both executors)
├── eval/                       # Phases 4–5
│   ├── benchmark/dev.yaml      # 34 questions — used for tuning
│   ├── benchmark/test.yaml     # 23 questions — held-out, never tuned on
│   ├── results/                # committed run reports (json + md), one per run
│   ├── triage/                 # human failure categories per run
│   └── CHANGELOG.md            # accuracy changes with before/after dev runs
├── frontend/                   # Vite + React + TS
│   └── src/                    # app, components, charts/selectChart.ts (done)
└── infra/
    ├── bootstrap/              # the Terraform state bucket (local state)
    └── main/                   # the stack, files split by concern (S3 backend)
```

---

## 5. Phases and milestones

A phase is done only when its milestone is met and CI is green.

| # | Phase | Deliverables | Milestone |
|---|---|---|---|
| 0 ✅ | **Scaffold** | ADRs; repo skeleton; backend project (uv, ruff, mypy, pytest, config module); Vite React TS app with Vitest; Terraform root skeleton; `ci.yml`; README | **Met:** all local checks that CI runs pass (backend lint/format/types/tests, frontend lint/types/tests/build, `terraform fmt`/`validate`); CI green on GitHub (PR #1) |
| 1 ✅ | **Data foundation (local)** | `docker-compose.yml`; pinned-checksum download; `raw` schema + load; 8 curated `analytics` views; `analytics_reader` role; initial `catalog.yaml` + drift test; `QueryExecutor` + `PostgresExecutor`; data-model / metrics / local-database docs; integration job in CI | **Met:** 168 integration tests pass from a clean volume; role tests prove no writes/DDL/raw access even with read-only disabled; revenue identical across all views and equal to an independent CSV recomputation; audit control totals reconcile exactly |
| 2 ✅ | **SQL safety + semantic validation** | Catalog relationships, visibility, function/cast allowlists; sqlglot validator with stable error codes; join-path + fan-out + attribution analysis; adversarial corpus; `sql-safety.md`; ADRs 0014–0015 | 100% of attack corpus rejected with a useful message; LIMIT always enforced; catalog drift test passes |
| 3 ✅ | **NL→SQL core** | `ModelClient` + Bedrock (bedrock-runtime) client + fake; catalog-generated prompt; pipeline with ≤ 1 repair; CLI `ask`; live smoke test | **Met:** fake model (unit + DB integration, all paths) and live model: `pytest -m live` 5/5 smoke questions answered end to end (Bedrock → validator → local DB) on Sonnet 4.6, 2026-10-11 |
| 4 ✅ | **Evaluation harness** | 50 drafted items (30 dev / 20 test) → **human verification** of each reference SQL/result; runner; result comparator; failure categoriser; report generator | **Met:** dev baseline 29/30 and held-out checkpoint 19/20 (Sonnet 4.6), both committed with triage |
| 5 ✅ | **Accuracy iteration (dev only)** | Catalog, view, prompt and few-shot changes driven by dev failure categories; optional second model via config | **Met:** dev 29/30 → 30/30 (prompt v2), [changelog](eval/CHANGELOG.md); held-out checkpoint 20/23 (original 20: 19/20, human-written 3: 1/3) |
| 6 ✅ | **Local API + UI** | `local_app.py`; React UI: access code, question box, table, auto chart, SQL panel, metrics and assumptions, truncation, error and "Starting analytics database..." states | **Met:** local demo against Docker Postgres + Bedrock Sonnet 4.6 (bar, line and KPI answers, unanswerable question, simulated resume, phone width); 505 backend unit tests incl. 24 API tests, 36 frontend tests (PR #4) |
| 7 ✅ | **AWS deployment** | **Entry condition:** root access keys deactivated and all AWS work through IAM users/roles (see §6). Terraform: state bucket, VPC (private subnets, S3 gateway endpoint), Aurora + Data API, secrets, `aws_s3` load, Lambda (+ reserved concurrency), HTTP API (+ throttling), logs/EMF/dashboard/alarms, $20 budget; `DataApiExecutor`; `/status` warm-up | **Met (2026-10-13):** executor contract 10/10 on Aurora through the Data API; eval smoke subset through the deployed API 8/8; cold start from a paused cluster: 503 `database_resuming`, then `/status` ready after 26.9 s, then answered |
| 8 ✅ | **Hosting + CD** | S3 + CloudFront (OAC); GitHub OIDC role; deploy workflow; manual eval workflow | **Met (2026-10-13):** Deploy #2 ran on its own after merging PR #7 (CI, then OIDC deploy, then smoke test); the public URL serves the app; no AWS keys are stored in GitHub |
| 9 ✅ | **Polish** | README with diagram, eval results (as measured), cost breakdown (as measured), security write-up, demo GIF | **Met (2026-10-14):** README opens with a demo GIF, a diagram and measured results; [architecture](docs/architecture.md), [costs](docs/costs.md) and [security](docs/security.md) write-ups; UI revamp live (PR #9); held-out checkpoint 21/23 |

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
| **AWS CLI currently uses root credentials** | **Entry condition for Phase 7** (Phase 7 does not start until it is met): create an IAM Identity Center (or IAM) admin user, use a named profile, lock away root keys (delete root access keys if any exist). *2026-10-08: IAM user + `olist-dev` profile in use.* **Met 2026-10-13:** both root access keys deactivated (credential report; a call with the root profile returns `InvalidClientTokenId`). Still to do outside this project: move another project's GitHub Actions deploy and the local `default` profile to IAM, then delete both root keys. |
| Dataset licence (CC BY-NC-SA 4.0) | Download script; never commit raw data; attribution in README |
| Model unavailability (happened: Sonnet 5 refused for the account, 2026-10) | Model ID only in config (`NLSQL_BEDROCK_MODEL_ID`, ADR 0019); after any model swap, re-baseline with a live smoke test, a fresh dev run and a held-out checkpoint, and report models separately |
| Held-out contamination from repeated checkpoints | Checkpoints only at phase ends, each recorded; never change anything because of a test result. **Checkpoints so far: 2** (end of Phase 4, end of Phase 5) |
| Small benchmark (34 dev / 23 held-out) | About 4.3 points per held-out item (about 2.9 per dev item), so differences of 1–2 items are not meaningful on their own; quote item counts, not just percentages, and repeat dev runs before claiming an improvement |

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

### Phase 9 (done, 2026-10-14)

- **Input:** 15 questions the owner asked on the live site. Q1–Q13 were correct.
  - Q14 (seller lead time): a false `FANOUT_RISK` rejection, 3/3.
  - Q15 (late vs on-time reviews within category and state): a 679-row table with
    no conclusion.
- **Benchmark:** dev-035 added from Q14. It was reworded by the owner, verified, and
  scored with the new `allow_negated` option (ADR 0017 amendment), so dev now has 35
  items. Q15 and two near-duplicates of held-out items stay out (ADR 0018 amendment).
- **Accuracy (dev evidence only, PR #9):**
  - **Validator:** `AVG`, `COUNT`, `STDDEV` and `PERCENTILE_CONT` of a one-side value
    are allowed when the many side is unique on its join keys plus its `GROUP BY`
    columns. `SUM` stays rejected (ADR 0014 amendment, 11 corpus cases, integration
    proof).
  - **Catalog:** the `average_delivery_delay_days` metric, and the delay sign spelled
    out on every delay column.
  - **Prompt v3:** association questions with controls answer with a summary row.
  - **API:** `/query` probes the database before the model call.
  - **Result:** dev 35, 35, 34 before and 35, 35, 35 after. I read this as no
    regression; the only difference is one flaky item. One run lost to a network
    outage was triaged and replaced.
- **UI revamp (PR #9):**
  - Sidebar with session history.
  - A "What can I ask?" panel generated from the catalog and the dev split, with a
    drift test.
  - Computed answer headline and takeaways, and a stats grid for one-row summaries
    (ADR 0007 amendment).
  - Sortable table with CSV export, and highlighted SQL with "Uses" chips.
  - Checked locally and on the live site after Deploy #4.
- **Part 2:**
  - Trend takeaways measure complete months only.
  - The start page no longer names the model, and the SQL view shows operators
    without ligatures.
  - Docs: [architecture.md](docs/architecture.md) with Mermaid diagrams,
    [costs.md](docs/costs.md), [security.md](docs/security.md), and the demo GIF in
    the README.
- **Measured costs (Cost Explorer, usage before credits):**
  - $3.63 from 2026-10-08 to 10-13, 94% of it Bedrock evaluation runs.
  - About $0.007 per question with a warm prompt cache, and about $0.03 for a lone
    question.
  - About $1.25 a month idle (3 secrets; a paused Aurora bills no compute), against
    the $2 estimate.
- **Held-out checkpoint:** 21/23 on clean `6223ef5`. The original 20 scored 19/20;
  the human-written 3 scored 2/3, up from 1/3. test-016 and test-021 failed as
  before. Nothing was changed because of it.
- **Open:**
  - The validator still rejects joins on computed keys, such as dev-017's
    `prev.month + INTERVAL '1 month'` and test-023's `rn = 1` / `rn = 2` pattern.
  - `NULLS LAST` in rankings still slips through (test-021).
  - Activating the `Project` cost-allocation tag would give per-project cost
    without the service-level split.

### Phase 8 (done, 2026-10-13)

- **Decisions:**
  - The UI and API share one origin: CloudFront serves the site and forwards `/api/*` to API Gateway, so there's no CORS and no API URL in the bundle.
  - The deploy workflow updates code only (UI to S3 plus a CloudFront invalidation, Lambda code) through a GitHub OIDC role scoped to those actions. Terraform stays a reviewed manual apply.
  - Repository variables are set by `gh`; the one secret (the deployed access code) is set by the owner.
- **Built and applied (2026-10-13):**
  - **Hosting:** CloudFront with a private site bucket behind origin access control, `/api/*` forwarded to API Gateway (a function strips the prefix) and security headers. Created in about 3 min.
  - **Deploy role:** GitHub OIDC provider plus a role trusted only for `main`, allowed only to deploy code.
  - **Workflows:** `deploy.yml` runs after CI on `main` (build, upload, update the Lambda, invalidate, smoke test); `eval.yml` runs a manual dev smoke through the public `/api`.
  - Terraform ignores the Lambda's code after the first apply.
  - The 6 repository variables are set. Guide: [docs/deployment.md](docs/deployment.md#hosting-and-continuous-deployment-phase-8).
- **First deploy:**
  - **Failed at OIDC.** This repository's tokens use GitHub's immutable subject (`repo:OWNER@ID/REPO@ID:...`), not the name-only form. The trust now uses the immutable prefix (PR #7), which also means a renamed or re-created repository with the same name can't deploy.
  - **The re-run passed**, smoke test included.
- **Live checks (2026-10-13, https://dunn64bzakzr8.cloudfront.net):**
  - HTTP redirects to HTTPS. CSP, HSTS, nosniff, `DENY` framing and referrer policy are on every response.
  - `index.html` is `no-cache`; the hashed JavaScript is cached for a year as immutable. The bundle doesn't contain the API Gateway URL.
  - `/api/status` gives 401 without the code and `resuming` on a paused database; `/api/admin` gives 404.
  - In the browser, the deployed access code was accepted. Requests stay on the same origin (`/api/status`, `/api/query`).
  - Top 5 categories: bar chart in 3.9 s, matching the local values. Orders per month in 2018: line chart, with the keyboard tooltip working under the CSP.
  - No console errors.
- **Automatic deploy on merge:** after PR #7 merged, CI ran on `main` and Deploy #2 started on its own and passed. That meets the milestone: a merge to `main` deploys, the public URL works, and no long-lived AWS keys are used.

### Phase 7 (done, 2026-10-13; CI green, PR #5)

- **Entry condition met:** root access keys deactivated (see §6).
- **Decisions:**
  - No reserved concurrency. The account's Lambda limit is 10, and AWS always keeps 10 unreserved, so API Gateway throttling plus the account cap are the ceiling (ADR 0004 amendment).
  - Auto-pause after 30 min idle.
  - Budget and alarm email kept in git-ignored `terraform.tfvars`.
- **Code:**
  - `DataApiExecutor`; the executor contract moved to `tests/executor_contract.py` and runs against both executors.
  - `lambda_handler` with EMF metrics (namespace `OlistNlSql`).
  - `scripts/build_lambda.py`: reproducible arm64 zip, 21.7 MB.
  - `dbsetup aws-build` / `aws-views`: aws_s3 imports through the Data API, with row counts verified.
  - `evaluation run --api-url` for runs against the deployed API.
- **Terraform:**
  - `infra/bootstrap`: the state bucket.
  - `infra/main`, 45 resources: VPC with private subnets and no NAT; Aurora Serverless v2 PG 16.15 at 0–2 ACU; secrets; data bucket; Lambda; HTTP API with throttling; alarms; dashboard; $20 budget.
  - CI validates both roots.
  - Guide: [docs/deployment.md](docs/deployment.md).
- **Applied 2026-10-13:**
  - Aurora writer created in 6.5 min.
  - `aws-build` loaded all 9 tables at their pinned counts, including `geolocation` at 1,000,163 rows.
- **Milestone checks:**
  - **Executor contract on Aurora:** 10/10.
  - **First requests:** `/status` 6.5 s (Lambda cold start), then 0.44 s; a wrong code gets 401; the first question was answered correctly in 2.3 s.
  - **Eval smoke subset through the API:** 8/8 (dev-002, 006, 007, 008, 012, 013, 021, 034), in [20261013T073332Z](eval/results/20261013T073332Z_dev_us-anthropic-claude-sonnet-4-6.md).
  - **Cold start after the 30-min auto-pause:**
    - `/query` returned 503 `database_resuming` in 13.4 s. That includes a Lambda cold start and one Bedrock call made before the database was reached.
    - `/status` polled `resuming` at 18 s and 23.5 s; no call took more than 4.6 s. It answered `ready` at 26.9 s.
    - The question asked again was answered correctly in 4.1 s.
- **Follow-up:** a `/query` that meets a paused database spends one Bedrock call before finding out. The UI checks `/status` first, so this only happens when the database pauses mid-session. Probing the database before the model call would save that call. This is a Phase 9 candidate, not a correctness issue.

### Phase 6 (done, 2026-10-13)

- **Aurora resume spike** ([docs/spikes/aurora-resume.md](docs/spikes/aurora-resume.md)): on a paused cluster, a Data API call fails fast with `DatabaseResumingException` (2.9–4.2 s, never more than 6.1 s), and queries succeed 16–20 s after the first call (5 trials, mean 18.2 s). The `/status` → "resuming" → poll design fits the 30 s API Gateway limit; `/query` must return a typed "resuming" error instead of waiting. **Deep sleep (2026-10-12, 1 trial, paused 25.3 h):** first success 81.9 s after the first call (19 calls); every call still failed fast (longest 6.9 s), so the design holds, but the UI must expect "Starting analytics database…" for about 80–90 s after a quiet day and keep polling for at least 2–3 minutes. The throwaway cluster `olist-resume-spike` and its secret were deleted on 2026-10-12.
- **API** (`olist_nlsql.api`, shared with the Phase 7 Lambda):
  - `GET /status` runs `SELECT 1` and answers ready or resuming without waiting.
  - `POST /query` takes a JSON body of at most 4 KiB with only `question`.
  - The access code is checked as a SHA-256 hash in constant time.
  - Pipeline status maps to HTTP status. A new `DatabaseResumingError` gives pipeline status `database_resuming`, sent as 503.
  - `local_app` runs it on loopback with the standard library (`serve`, `--fake-sql`, `--simulate-resume`, `hash-code`).
- **UI:**
  - Access-code gate, using `sessionStorage`.
  - A "Starting analytics database…" state that polls every 3 s, shows elapsed time, adds a long-start message after 30 s and gives up after 3 min. A question that hits a resuming database is asked again once it is ready.
  - Question box with a 500-character limit and dev-split examples.
  - Interpretation, metrics, assumptions, SQL panel, truncation notice, and empty and failure states.
- **Charts (ADR 0007, `selectChart.ts`):** KPI tile, line chart, bar chart (horizontal for long labels), otherwise a table, which is always one click away. Hand-drawn SVG, with hover and keyboard tooltips. Two refinements to the ADR rules:
  - `YYYY-MM` text from `TO_CHAR` counts as time.
  - Series that differ more than 10× in scale become small multiples instead of a second axis.
- **Tests:** 24 API unit tests, including a real HTTP round trip, and 36 frontend tests covering chart rules, formatting, charts and app flows with mocked `fetch` and fake timers.
- **Local demo (2026-10-13), Docker Postgres + Bedrock Sonnet 4.6, in the in-app browser:**
  - Access code accepted; a wrong code gets 401.
  - Top 5 categories by revenue: horizontal bar chart in 4.0 s, values match the dev reference.
  - Orders per month in 2018: line chart, with the incomplete-month assumption shown.
  - Late delivery rate: KPI tile, 6.77%.
  - Names and emails of customers: shown as unanswerable.
  - `--simulate-resume 20`: the starting screen, then ready.
  - 375 px phone width: no horizontal scroll. Bar labels and ticks were fixed after this check.

### Phase 5 (done, 2026-10-11)

- Changes and before/after dev runs are logged in [eval/CHANGELOG.md](eval/CHANGELOG.md).
- **Prompt v2** (dev-012): ranking by a NULL-able aggregate must filter `is_revenue_order` or use `NULLS LAST`; same caveat on the `revenue` metric. Dev **29/30 → 30/30** ([20261009T091218Z](eval/results/20261009T091218Z_dev_us-anthropic-claude-sonnet-4-6.md)), no regressions.
- **Variance (2026-10-11):** four dev runs on v2 scored 30, 30, 30, 28; the SQL logic was the same in every run. Both misses were 2-decimal rounding against a 0.0005 tolerance, so review-score averages (dev-005, dev-013, dev-020, test-008, test-011) now use the default 0.005 and were re-verified.
- **Human-written items (2026-10-11):** 7 hand-written questions added and verified (dev-031–034, test-021–023; [ADR 0018](docs/adr/0018-human-written-benchmark-items.md), splits now 34 / 23); an eighth dropped as a near-duplicate of test-008. New dev baseline **34/34** ([20261011T205414Z](eval/results/20261011T205414Z_dev_us-anthropic-claude-sonnet-4-6.md)).

- **Held-out checkpoint (2026-10-11):** [20261011T205637Z](eval/results/20261011T205637Z_test_us-anthropic-claude-sonnet-4-6.md), **20/23**. Original 20 items unchanged at 19/20 (test-016 again). Human-written items 1/3: test-021 ranked NULL monthly revenue first (dev-012's mechanism, outside the v2 rule's example), test-023 was a false `INVALID_JOIN_PATH` rejection. Not acted on (held-out).
- Caveat for reporting: the human-written items were clearly harder than the drafted ones; quote the split, not only 87%.

**Next steps:**
1. Phase 6 (local API + UI).
2. Accuracy work later must come from dev evidence. dev-034's first-attempt `INVALID_JOIN_PATH` rejection is dev evidence about the validator's handling of per-customer CTE joins.
3. Optional second model via config.

### Phase 4 (done, 2026-10-09)

**Where it stands:** milestone met; dev baseline and one held-out checkpoint committed.

- Harness in `olist_nlsql.evaluation`: strict benchmark loader, comparator, runner, failure categoriser, markdown report with triage overrides; CLI `python -m olist_nlsql.evaluation check|snapshot|show|verify|run|report` ([eval/README.md](eval/README.md)).
- ADR 0017: comparison rules (names/column order ignored, extra columns allowed, percent form for rates, month normalisation, per-item tolerances) and verification pinned to a content hash.
- 50 items (30 dev / 20 test) across all ADR 0006 areas and difficulties. Snapshots taken on the pinned Kaggle build. Review changed dev-010 (wording), dev-020 (exclude `uncategorized`) and dev-024 ("sold" = revenue orders, 3,053).
- **All 50 items human-verified** (Shubham More). Test review changed test-008 (label column dropped so boolean or text group labels both match), test-009 ("bought something" → "placed an order", any status as in dev-029) and test-017 ("how much" → "by what percentage"). Ties and near-boundary rows checked for every ranking; `uncategorized` is in no top-k.
- **Model:** Sonnet 5 is blocked for the account ("not available for this account… contact AWS Sales"; use-case form submitted 2026-10-08, Support case pending). Runs use **`us.anthropic.claude-sonnet-4-6`** via `NLSQL_BEDROCK_MODEL_ID`, no code change. Recorded as the current model in ADR 0019 (2026-10-11).
- Live fixes from the first runs: the parser keeps `assumptions`/`metrics_used` sent as (possibly malformed) text instead of failing the question; prompt-cache tokens are now recorded.
- **First dev baseline:** [20261009T082119Z](eval/results/20261009T082119Z_dev_us-anthropic-claude-sonnet-4-6.md), Sonnet 4.6, **29/30 correct**. Miss: dev-012, triaged `wrong_filter_or_time_window` (no revenue-order filter, so NULL-revenue sellers sort first in `ORDER BY DESC`).
- **Held-out checkpoint:** [20261009T083443Z](eval/results/20261009T083443Z_test_us-anthropic-claude-sonnet-4-6.md), Sonnet 4.6, **19/20 correct**. Miss: test-016, triaged `wrong_filter_or_time_window` (averaged `item_count` over all orders, including the 775 with no items). Not acted on (held-out). The record shows "uncommitted changes" because verification of test.yaml was committed together with the run; the benchmark hash pins the content.
- Caveat for reporting: questions were drafted with Claude's help and are answered by a Claude model; references are human-verified, but a few human-written test questions would strengthen the held-out result.

**Next steps:**
1. Phase 5 (dev only): catalog/prompt line saying rankings by revenue must filter `is_revenue_order` or use `NULLS LAST` (from dev-012); re-run dev and compare.

### Phase 3 (done, 2026-09-24)

- Pipeline: catalog prompt → Bedrock (bedrock-runtime, forced tool call) → validator → at most one repair → `analytics_reader` → typed result; ≤ 2 model calls enforced and tested.
- Prompt v1 generated from the catalog: ≈ 22.9k chars / ≈ 5.7k tokens; hidden relations absent (tested).
- Distinct failure statuses incl. `validator_error` (new `VALIDATOR_INTERNAL_ERROR` code, traceback logged only) and non-repairable writes.
- Validator made idempotent (LIMIT up to max_rows + 1 accepted) after a pipeline test showed its own output failed re-validation.
- CLI `python -m olist_nlsql ask|prompt` with `--json`, `--show-prompt`, `--fake-sql`.
- 663 tests pass (unit + integration); live smoke test skips: **Bedrock model access not yet granted** (`agreementAvailability: NOT_AVAILABLE`).
- *2026-10-11:* live smoke test passes, 5/5, on `us.anthropic.claude-sonnet-4-6` (Sonnet 5 still unavailable to the account).
- ADR 0016: bedrock-runtime + `AnthropicBedrock` + `us.anthropic.claude-sonnet-5` + forced tool call. The first draft (Mantle + `output_config.format`) was corrected after checking AWS docs: structured outputs are unsupported for Sonnet 5 on Bedrock and would have returned 400.

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
- [x] CI green on GitHub (first green run: PR #1, 2026-10-11)
