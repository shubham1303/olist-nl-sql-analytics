# Deployment (AWS)

Phase 7 runs the same pipeline on AWS: API Gateway (HTTP API) → Lambda (Python 3.13,
arm64, outside any VPC) → Bedrock and the RDS Data API → Aurora Serverless v2
PostgreSQL in private subnets. Terraform lives in [infra/](../infra).

Every command below uses an IAM user profile (`AWS_PROFILE=olist-dev`), never root
credentials (plan.md §6).

## First deploy

1. **State bucket** (once):

   ```sh
   cd infra/bootstrap
   terraform init && terraform apply
   ```

2. **Settings:** copy `infra/main/terraform.tfvars.example` to `terraform.tfvars`
   (git-ignored). It needs `alert_email`, plus `access_code_sha256` from
   `python -m olist_nlsql.api hash-code`. Keep the code itself in `.env` as
   `NLSQL_API_ACCESS_CODE`.

3. **Lambda package:**

   ```sh
   cd backend
   uv run python scripts/build_lambda.py        # backend/build/lambda.zip, reproducible
   ```

4. **Stack:**

   ```sh
   cd infra/main
   terraform init -backend-config="bucket=$(terraform -chdir=../bootstrap output -raw state_bucket)"
   terraform plan -out=main.tfplan
   terraform apply main.tfplan
   terraform output -raw env >> ../../.env      # NLSQL_DB_* and the data bucket (account-specific)
   ```

   Aurora takes about 7 minutes to create. AWS emails `alert_email` a subscription
   confirmation for the alarm topic. Click it, or alarms won't be delivered.

5. **Data:** upload the pinned CSVs and build the database through the Data API
   (about 3 minutes):

   ```sh
   cd backend
   uv run python -m olist_nlsql.dbsetup aws-build
   ```

   Every table must match its pinned row count, or the build stops. `aws-views`
   rebuilds only the analytics layer.

## Checks

```sh
cd backend
uv run pytest -m live tests/live/test_data_api_executor.py   # executor contract on Aurora
uv run python -m olist_nlsql.evaluation run --split dev \
    --api-url "$(terraform -chdir=../infra/main output -raw api_url)" dev-002 dev-006 ...
```

The live contract test resumes a paused cluster first.

## Updating

- **Code:** rebuild the zip, then `terraform plan`/`apply` (only the function changes;
  an unchanged build is the same zip, so there's no diff).
- **Views:** `dbsetup aws-views`.
- **Model:** `bedrock_model_id` in `terraform.tfvars` (ADR 0019: the IAM policy
  follows; re-baseline afterwards).
- **Rotating the reader password:** `terraform apply -replace=random_password.reader`,
  then `dbsetup aws-build`.

## What it costs

| While idle | |
|---|---|
| Aurora | Storage only (about 0.2 GB) while paused at 0 ACU |
| Secrets Manager | 3 secrets (owner, reader, RDS-managed master) |
| CloudWatch | 5 alarms, 1 dashboard, logs kept 14 days |
| Network | No NAT, no interface endpoints; the S3 gateway endpoint is free |

When used, Aurora is billed per ACU-hour while awake (it pauses after 30 min idle),
Bedrock per token (about 7k input, mostly cached, and 250 output per question), and
Lambda and API Gateway per request.

The $20 budget emails at 50/80/100% of actual spend and at a forecast of 100%. It's an
alert, not a cap: the throttles are the real controls (ADR 0004).

## Cold starts

After 30 min idle the cluster pauses. The first `/status` or `/query` starts a resume:

- **`/status`** answers `{"db": "resuming"}` at once, and the UI polls it every 3 s.
- **`/query`** answers 503 `database_resuming`.

Resume takes about 20 s after a short pause and about 80–90 s after a day
([spikes/aurora-resume.md](spikes/aurora-resume.md)).
