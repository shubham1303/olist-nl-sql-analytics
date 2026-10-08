# Local development

Everything runs on a laptop: Docker PostgreSQL for data, real Amazon Bedrock for the
model (or `--fake-sql` offline). AWS is used only for Bedrock calls until Phase 7.

## One-time setup

| Tool | Version | Notes |
|---|---|---|
| uv | recent | Installs Python 3.13 for the backend |
| Node.js | 24 LTS | `.nvmrc` |
| Docker | recent | Local PostgreSQL 16 |
| Terraform | ≥ 1.10 | `infra/` checks only, for now |
| AWS CLI v2 | recent | Bedrock authentication |

```sh
cp .env.example .env                  # database passwords only; never AWS credentials
docker compose up -d --wait
cd backend
uv sync
uv run python -m olist_nlsql.dbsetup download
uv run python -m olist_nlsql.dbsetup build
uv run pytest                         # unit tests: no database, no AWS
uv run pytest -m integration          # needs the local database
```

The database is covered in detail in [local-database.md](local-database.md).

## AWS authentication for Bedrock

The application uses the **standard AWS credential chain**. It never reads AWS keys
from `.env` or code.

1. Use a named profile for an IAM Identity Center (SSO) user or an IAM user, **not the
   account root user**:

   ```sh
   aws configure sso                    # or: aws configure --profile olist-dev
   aws sso login --profile olist-dev
   export AWS_PROFILE=olist-dev          # PowerShell: $env:AWS_PROFILE = "olist-dev"
   aws sts get-caller-identity          # check who you are
   ```

2. The identity needs `bedrock:InvokeModel` for the `us.anthropic.claude-sonnet-5`
   inference profile and the foundation models it routes to. The application calls the
   **bedrock-runtime** endpoint (ADR 0016). The least-privilege policy is written in
   Phase 7.

3. **Model access.** Bedrock enables serverless models automatically, but Anthropic
   models need a **one-time use-case form** per account:
   1. Check whether it's on file: `aws bedrock get-use-case-for-model-access --region us-east-1`.
      `ResourceNotFoundException` means it was never submitted.
   2. Submit it, either by opening Claude in the Bedrock playground (`us-east-1`) when the
      console offers the form, or from the CLI with a JSON file holding `companyName`,
      `companyWebsite`, `intendedUsers`, `industryOption`, `otherIndustryOption` and
      `useCases`:

      ```sh
      aws bedrock put-use-case-for-model-access --form-data fileb://bedrock-form.json --region us-east-1
      ```

   3. Make the first call as an identity with AWS Marketplace permissions (an admin user):
      it accepts the model's Marketplace offer for the account.
   4. Check with:

   ```sh
   # The control-plane check uses the foundation-model ID (no us./global. prefix):
   aws bedrock get-foundation-model-availability \
       --model-id anthropic.claude-sonnet-5 --region us-east-1
   ```

   `agreementAvailability.status` must not be `NOT_AVAILABLE`. Until access is granted,
   the CLI reports `generation_failed / access_denied` and `pytest -m live` skips.

   An `AccessDeniedException` saying the model "is not available for this account …
   contact AWS Sales" is an account-level entitlement block. IAM and console settings
   can't clear it; open an AWS Support case (Account and billing).

Model settings are environment variables (defaults in
[config.py](../backend/src/olist_nlsql/config.py)):

| Variable | Default | Meaning |
|---|---|---|
| `NLSQL_AWS_REGION` | `us-east-1` | Bedrock region |
| `NLSQL_BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-5` | bedrock-runtime inference profile (US geo). `global.anthropic.claude-sonnet-5` also works. The bare ID doesn't (ADR 0016). |
| `NLSQL_LLM_EFFORT` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` |
| `NLSQL_LLM_THINKING` | `disabled` | `disabled` forces the `submit_answer` tool call. `adaptive` enables thinking and asks for the call instead. |
| `NLSQL_LLM_MAX_OUTPUT_TOKENS` | `4096` | Output cap per call, thinking included |
| `NLSQL_LLM_TIMEOUT_SECONDS` | `60` | Per-call timeout |
| `NLSQL_MAX_QUESTION_CHARS` | `500` | Longer questions are rejected before any call |
| `NLSQL_MAX_RESULT_ROWS` | `1000` | Row cap (hard ceiling 1,000) |

## Running the pipeline

```sh
cd backend
uv run python -m olist_nlsql ask "What was merchandise revenue in 2017?"
uv run python -m olist_nlsql ask "..." --json
uv run python -m olist_nlsql ask "..." --fake-sql "SELECT SUM(revenue) AS revenue FROM orders"
uv run python -m olist_nlsql prompt --stats
```

See [nl-to-sql.md](nl-to-sql.md) for the flow, the result fields and the failure
modes.

## Tests

| Command | Needs | What it covers |
|---|---|---|
| `uv run pytest` | nothing | Unit tests: validator corpus, prompt, parser, pipeline with a fake model |
| `uv run pytest -m integration` | Docker database | Data model, permissions, validator vs database, pipeline end to end with a fake model |
| `uv run pytest -m live -s` | AWS credentials and model access | 5-question Bedrock smoke test; prints outcomes; skips if unavailable |

The benchmark has its own commands; see [eval/README.md](../eval/README.md).

The live tests never run in CI.
