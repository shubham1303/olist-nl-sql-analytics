# 0002. The database is the primary security boundary; sqlglot validation is layer two

- Status: Accepted
- Date: 2026-09-23

## Context

The system runs SQL written by an LLM from untrusted user input. SQL parsers and
validators can be bypassed or can drift from the engine's grammar. A validator alone
isn't a defensible security boundary.

## Decision

Security is layered. Each layer must hold on its own:

1. **Database role `analytics_reader`:**
   - `USAGE` on schema `analytics` and `SELECT` on its views only. No access to raw or
     internal schemas. `PUBLIC` privileges are revoked on the database and schemas.
   - Owns nothing, so it can't run DDL. It has no `INSERT/UPDATE/DELETE/TRUNCATE`
     grants, so it can't run DML.
   - `ALTER ROLE ... SET default_transaction_read_only = on` and
     `SET statement_timeout = '10s'` (the exact value is tunable).
   - Not a superuser, and not `CREATEDB`, `CREATEROLE` or `REPLICATION`.
2. **IAM (Lambda execution role):**
   - `rds-data:ExecuteStatement` (plus the statement/transaction actions the executor
     actually uses) on **the one cluster ARN**.
   - `secretsmanager:GetSecretValue` on **the one secret** holding the
     `analytics_reader` credentials.
   - No access to the admin/master secret. Bedrock invoke is scoped to the configured
     inference profile and its underlying model ARNs.
3. **SQL validation (sqlglot, Postgres dialect):**
   - Exactly one statement, and it must be a `SELECT` (CTEs allowed, data-modifying
     CTEs rejected).
   - Relations and columns must be on the catalog allowlist ([ADR 0005](0005-curated-analytics-schema-and-catalog.md)).
   - Functions must be on an **allowlist**, not a denylist.
   - No system catalogs, no `SELECT INTO`, no locking clauses.
   - `LIMIT` is injected or clamped to the row maximum.
   - Rejections return a machine-readable code and a human-readable message.
4. **Execution limits:** the statement timeout, a row cap (1,000) and a column cap.

## Consequences

- A validator bug degrades the user experience but not security. Integration tests
  must prove that `analytics_reader` can't write, alter, read raw schemas, or escape
  read-only mode.
- Local Docker Postgres uses the same role script as Aurora, so security behaviour is
  tested locally.
- The validator must accept every verified reference query. False rejections count as
  bugs.
