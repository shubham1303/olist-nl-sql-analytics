# Security

This app takes free text from strangers, hands it to an LLM, and runs the SQL that
comes back against a real database. This page covers what could go wrong and what
stops it. Each control below names the code or Terraform that implements it and the
test that proves it.

## What I'm protecting against

| Threat | Example |
|---|---|
| **Writes or escapes through SQL** | A question (or a prompt injection inside one) gets the model to emit `DROP`, `UPDATE`, `COPY ... TO PROGRAM`, `pg_read_file`, a data-modifying CTE, or `SELECT` from the raw schema |
| **Wrong answers that look right** | A join that double counts revenue (fan-out), or an order-level outcome repeated per seller and averaged as if it weren't |
| **Resource abuse** | Very slow queries, huge results, or a stream of requests that runs up the Bedrock bill |
| **Leaking data the model shouldn't see** | The raw tables, hidden views, or the result rows themselves reaching the model |
| **Credential and deploy compromise** | Long-lived AWS keys in GitHub, an over-privileged Lambda or deploy role, root keys |
| **The usual web risks** | XSS, clickjacking, an open API anyone can call |

## Layers, from the inside out

### 1. The database role is the boundary (ADR 0002)

Queries run as `analytics_reader`, which:
- can `SELECT` from the `analytics` views only, with no access to `raw` or the system
  catalogs beyond what PostgreSQL grants every role;
- has `default_transaction_read_only = on`, a 10 s `statement_timeout`, and a
  connection limit;
- has no `CREATE` anywhere, and `PUBLIC` loses its default rights on the database and
  the `public` schema.

This holds even if every other layer fails.
[test_validator_execution.py](../backend/tests/integration/test_validator_execution.py)
sends 18 attacks (writes, DDL, `GRANT`, `COPY`, file reads, raw-schema reads,
`SELECT ... FOR UPDATE` and more) straight to the database with the validator
bypassed. The role rejects every one.
[test_permissions.py](../backend/tests/integration/test_permissions.py) also switches
the session to read-write and shows DDL and DML are still refused by privileges.

### 2. The validator decides what runs (ADR 0014)

[sqlsafety/](../backend/src/olist_nlsql/sqlsafety/) parses the model's SQL with sqlglot
and allows only:
- exactly one `SELECT` (CTEs allowed), with no `INTO`, locking clauses or
  data-modifying CTEs;
- catalog views and model-visible columns, with every function and cast on an
  allowlist (no `pg_sleep`, `current_user`, file or network functions);
- joins along catalog relationships only, rejecting fan-out and attribution errors
  (`FANOUT_RISK`) with a message that says how to fix them;
- at most 8,000 characters and 6 joins, and a `LIMIT` of at most 1,000 rows that the
  validator adds itself.

The SQL that runs is the validator's regenerated text, never the model's original
string. The regeneration round-trip is checked, and any escape-string form sqlglot
can't reproduce exactly is refused. The corpus
([sql_cases.py](../backend/tests/sql_cases.py), about 200 cases) holds accepted
queries that must also execute, and rejected ones with their expected error code.
Several rejected queries are valid SQL that returns an inflated number; the
integration suite proves the inflation.

### 3. The model sees the schema, never the data (ADR 0005, 0015)

The system prompt is generated from [catalog.yaml](../backend/src/olist_nlsql/catalog/catalog.yaml)
and lists only exposed relations and columns. The pre-aggregated `customers` and
`sellers` views and the product-level totals are hidden. They invite double counting
when joined back to orders, so the model never hears of them, and the validator
rejects them if it guesses (ADR 0015). Free text such as review comments isn't in the
analytics views at all, only a `has_comment` flag. Result rows never go back to the model: answer
headlines and charts are computed in the browser. The "What can I ask?" panel is
generated from the same exposed subset, and a test fails if a hidden column appears
in it.

### 4. The API limits who and how much (ADR 0004)

- **Access code.** Every request needs `X-Access-Code`. The Lambda stores only a
  SHA-256 digest and compares in constant time (`hmac.compare_digest`). Without a
  configured digest the API refuses to start.
- **Bounds.** Requests are capped at 4 KB, questions at 500 characters, and model
  calls at 2 per question. Output tokens are bounded, and the Lambda times out at 29 s.
- **Throttling.** API Gateway allows 2 requests/s overall and 1/s on `/query`.
- **Paused database.** `/query` checks the database is awake before calling the model,
  so a paused database can't be used to burn Bedrock calls.
- **Monitoring.** Alarms on errors, throttles, 5xx and model failures, plus a $20
  budget, all email me.

### 5. Least-privilege AWS (Phases 7–8)

- **Lambda role:**
  - `rds-data:ExecuteStatement` on this one cluster;
  - `secretsmanager:GetSecretValue` on the reader secret only;
  - `bedrock:InvokeModel` on the one model's inference profile;
  - writing to its own log group.

  It has no VPC access and no S3 access.
- **Deploy role (GitHub OIDC):**
  - It trusts only this repository's `main` branch, through GitHub's immutable
    repository-ID subject, not the renamable `owner/repo` name.
  - Its actions are limited to writing the site bucket, invalidating the CloudFront
    distribution, and updating the one Lambda's code. It cannot change infrastructure
    or IAM.
  - No AWS keys are stored in GitHub.
- **Network:** Aurora sits in private subnets with no public endpoint, reachable only
  through the Data API.
- **Accounts:** both root access keys are deactivated, and all work goes through an
  IAM user. Terraform is applied by hand after reviewing the plan.

### 6. The browser (Phase 8)

CloudFront serves the app and the API from one origin and adds headers to every
response:
- a strict Content-Security-Policy: `default-src 'self'`, scripts from self only,
  `connect-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`;
- HSTS (1 year, subdomains), `nosniff`, `X-Frame-Options: DENY`, and a strict referrer
  policy.

The S3 bucket is private and reachable only through CloudFront (origin access
control). React escapes all model and database text, the app uses no
`dangerouslySetInnerHTML`, and the SQL highlighter builds React elements from tokens.
The access code and the question history live in `sessionStorage` and disappear with
the tab. CSV exports neutralise spreadsheet formulas (`=`, `+`, `-`, `@`).

## Known gaps and trade-offs

- **The access code is shared.** It isn't per-user authentication, and rotating it
  means updating the digest and redeploying. That's fine for a portfolio demo, but
  not for real users. Cognito or similar would be the next step.
- **Questions are logged** to CloudWatch, without result rows, for 14 days, so I can
  debug and measure. Anyone using the demo should treat their questions as visible
  to me.
- **`style-src 'unsafe-inline'`** stays because React sets inline style attributes
  for tooltip positions. Scripts are not affected.
- **A correct-looking wrong answer is still possible.** The validator catches
  structural errors (fan-out, attribution), not wrong filters or a wrong choice of
  metric. The [evaluation harness](../eval/README.md) measures how often that
  happens, and every answer shows its SQL, metrics and assumptions so a reader can
  check.
- **No WAF.** API Gateway throttling and the budget are the abuse controls. A WAF
  would cost more per month than the whole idle stack ([costs.md](costs.md)).
