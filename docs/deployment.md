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

## Hosting and continuous deployment (Phase 8)

The public app is CloudFront (`terraform output -raw site_url`) in front of:

- **the private site bucket**, read through origin access control;
- **the HTTP API** under `/api/*`, with no caching and all viewer headers except `Host`.
  A CloudFront function strips the `/api` prefix, so the browser only ever talks to one
  origin: no CORS, and no API URL in the bundle.

Every response carries security headers (CSP, HSTS, `nosniff`, `X-Frame-Options:
DENY`).

**Deploys** (`.github/workflows/deploy.yml`) run after CI passes on a push to `main`,
or by hand from the Actions tab:

1. Build the UI and the Lambda zip from the commit CI tested.
2. Assume the deploy role through GitHub OIDC. No AWS keys are stored in GitHub.
3. Upload the UI. Hashed assets are cached for a year; `index.html` is always
   revalidated.
4. Update the Lambda code and wait for it to become active.
5. Invalidate `/index.html`.
6. Smoke test: the site returns 200, and `/api/status` without a code returns 401.

The deploy role (`infra/main/github.tf`) trusts only this repository's `main` branch.
This repository uses GitHub's immutable OIDC subject, which includes the owner and
repository IDs (`repo:shubham1303@23360808/olist-nl-sql-analytics@1384310424:ref:refs/heads/main`).
A renamed or re-created repository with the same name can't deploy. If you fork this
project, set `github_oidc_sub_prefix` to your repository's `sub_claim_prefix` (from
`gh api repos/OWNER/REPO/actions/oidc/customization/sub`).
It can write the site bucket, invalidate the distribution and update the function's
code, and nothing else. Terraform ignores the function's code after the first apply,
so the two don't fight. Infrastructure changes stay a reviewed, manual `terraform
apply`.

**Repository settings** the workflows read:

| Kind | Name | Value |
|---|---|---|
| Variables | `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `SITE_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `LAMBDA_FUNCTION_NAME`, `SITE_URL` | `terraform output -json github_variables` |
| Secret | `NLSQL_API_ACCESS_CODE` | The deployed access code (used only by `eval.yml`) |

**Eval smoke** (`.github/workflows/eval.yml`, manual) asks dev questions through the
public `/api` and uploads the run records as an artifact. It runs on the dev split only
and needs no AWS credentials.
