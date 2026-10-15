# Architecture

Two views: where things run, and what happens to one question. The reasons behind
each choice are in the [ADRs](adr/README.md).

## Where things run

```mermaid
flowchart LR
  user([Browser])
  subgraph edge[CloudFront, one origin]
    cf[Distribution<br/>CSP + security headers]
    fn[Function: strip /api]
  end
  s3[(S3, private<br/>React app)]
  apigw[API Gateway HTTP API<br/>throttled 2/s, /query 1/s]
  lambda[Lambda, Python 3.13 arm64<br/>outside the VPC]
  bedrock[Bedrock<br/>Claude Sonnet 4.6]
  dataapi[RDS Data API]
  subgraph vpc[VPC, private subnets]
    aurora[(Aurora Serverless v2<br/>PostgreSQL 16, 0-2 ACU<br/>pauses after 30 min)]
  end
  secrets[Secrets Manager<br/>reader secret]
  cw[CloudWatch<br/>logs, EMF metrics, alarms]
  gh[GitHub Actions<br/>CI, then deploy via OIDC]

  user --> cf
  cf -- "/" --> s3
  cf -- "/api/*" --> fn --> apigw --> lambda
  lambda --> bedrock
  lambda --> dataapi --> aurora
  dataapi -.-> secrets
  lambda -.-> cw
  gh -. "upload site, update code" .-> s3
  gh -.-> lambda
```

- **One origin.** The browser only ever talks to CloudFront. `connect-src 'self'` in
  the CSP is enough, and there's no CORS to configure.
- **No VPC Lambda, no NAT gateway.** The Lambda reaches Aurora through the Data API
  over HTTPS, using the reader's secret. It never holds a database connection, so
  Aurora can pause.
- **Scale to zero.** When Aurora is paused, `/status` answers `resuming` straight
  away. The UI polls it and shows "Starting analytics database…" until it's ready,
  because a resume takes 20–90 s and API Gateway gives up after 30 s
  ([spike](spikes/aurora-resume.md)).
- **Code-only deploys.** Every merge to `main` runs CI, then `deploy.yml` uploads the
  site and updates the Lambda code with short-lived OIDC credentials. Infrastructure
  changes go through `terraform plan` and a manual apply.

## One question, end to end

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser
  participant L as Lambda (/query)
  participant M as Bedrock (Claude)
  participant V as Validator (sqlglot)
  participant D as Aurora (analytics_reader)

  B->>L: POST /query {question} + X-Access-Code
  L->>L: check code digest, size, length
  L->>D: SELECT 1 (awake?)
  alt database paused
    D-->>L: resuming
    L-->>B: 503 database_resuming (no model call)
  end
  L->>M: catalog prompt (cached) + question
  M-->>L: submit_answer {sql, interpretation, assumptions, metrics}
  L->>V: validate(sql)
  alt rejected, repairable
    V-->>L: error code + fix instruction
    L->>M: one repair request
    M-->>L: corrected answer
    L->>V: validate again
  end
  V-->>L: regenerated SQL, row limit enforced
  L->>D: execute (read-only, 10 s timeout)
  D-->>L: rows (≤ 1,000 shown, truncation flagged)
  L-->>B: answer: rows, SQL, interpretation, assumptions, timings
  B->>B: pick chart, headline, takeaways (no model)
```

What each step guarantees:

| Step | Guarantee | Where |
|---|---|---|
| Prompt | The model only sees exposed views, columns, relationships and metric definitions, generated from one catalog | [prompts.py](../backend/src/olist_nlsql/llm/prompts.py), [catalog.yaml](../backend/src/olist_nlsql/catalog/catalog.yaml) |
| Model call | A forced `submit_answer` tool call, parsed strictly, at most 2 calls per question | [bedrock.py](../backend/src/olist_nlsql/llm/bedrock.py), [pipeline.py](../backend/src/olist_nlsql/pipeline.py) |
| Validation | Single SELECT, allowlisted views, columns and functions, catalog joins only, no fan-out, LIMIT enforced, rankings sort NULLs last | [sql-safety.md](sql-safety.md) |
| Execution | The validator's SQL, never the model's text, as a read-only role on the analytics views only | [security.md](security.md) |
| Presentation | Chart, headline and takeaways computed from the rows in the browser; SQL and assumptions always shown | [selectChart.ts](../frontend/src/charts/selectChart.ts), [summary.ts](../frontend/src/lib/summary.ts) |

## Locally

The same pipeline runs against Docker Postgres with `PostgresExecutor` in place of
the Data API ([local-development.md](local-development.md)). The evaluation harness
uses that path, or a deployed API with `--api-url`, so a benchmark run exercises
exactly the code that serves the site.

```mermaid
flowchart LR
  cli[CLI ask / eval runner] --> pipe[NlSqlPipeline]
  ui[Vite dev server :5173] -- /api proxy --> api[local_app :8000] --> pipe
  pipe --> bedrock[Bedrock]
  pipe --> pg[(Docker Postgres 16<br/>same views and roles)]
```
