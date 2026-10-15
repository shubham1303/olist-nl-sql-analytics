# Costs (measured)

These are what AWS actually billed, not list-price estimates. All of it so far was
covered by promotional credits, so the figures below are **usage before credits**.

Source: Cost Explorer, `RECORD_TYPE = Usage`, read on 2026-10-14. Cost Explorer lags
by about a day and marks the current month as estimated. The stack has existed since
2026-10-11, so this is a few days of data, not a month.

## So far (2026-10-08 to 2026-10-13)

| Service | Usage cost | What it was |
|---|---:|---|
| Bedrock, Claude Sonnet 4.6 | $3.39 | Mostly evaluation: 10 full dev runs, 2 held-out checkpoints, smoke tests |
| Aurora Serverless v2 (RDS) | $0.21 | ACU-hours while awake (building the database, eval runs through the API), plus I/O and storage |
| Secrets Manager | $0.03 | Database secrets, prorated from creation |
| S3, API Gateway, Lambda, CloudFront, CloudWatch, KMS | < $0.01 | Inside the free tier at this volume |
| **Total** | **$3.63** | 94% of it is the model |

The account also shows a few cents for Cognito, Glue and DynamoDB. Those belong to
another project in the same account and are left out. These figures are split by
service. Since 2026-10-15 the `Project` tag is an active cost-allocation tag (Terraform:
`aws_ce_cost_allocation_tag.project`), backfilled from 2026-10-01, so the project can
be filtered directly with `Project = olist-nlsql` (see below).

## Per question

From the token counts in the three Phase 9 dev runs (105 questions, prompt v3), at
Sonnet 4.6 list prices on Bedrock ($3 per million input tokens, $15 per million
output, $0.30 per million cache reads, $3.75 per million cache writes):

| | Tokens per question | Cost |
|---|---:|---:|
| System prompt (catalog), read from cache | 6,676 | $0.0020 |
| Question and tool schema, uncached | ~515 | $0.0015 |
| Output (SQL, interpretation, assumptions) | 255 | $0.0038 |
| **Back-to-back questions** (cache warm) | | **≈ $0.007** |
| **A lone question** (cache expired after 5 min: writes 6,613 tokens) | | **≈ $0.03** |

There are 1.02 model calls per question, because a repair is rare. The median
end-to-end time was 2.5 s and the 90th percentile 3.9 s, measured locally against
Docker Postgres.

Cross-check: a 35-question dev run comes to about $0.26 by this table. On 2026-10-13,
one run plus smoke tests billed $0.38.

## Idle

The database pauses after 30 minutes without connections and costs nothing for
compute while paused. What remains:

| Item | Per month |
|---|---:|
| 3 Secrets Manager secrets (Aurora-managed master, owner, reader) at $0.40 | $1.20 |
| Aurora storage (well under 1 GB) and backups within the retention allowance | ≈ $0.02 |
| 5 alarms, 1 dashboard, logs, S3, CloudFront, API Gateway, Lambda | ≈ $0 (free tier) |
| **Idle total** | **≈ $1.25** |

Before deployment I estimated about $2 a month. The measured idle cost is lower,
because the paused cluster really bills no ACU-hours. Oct 12, a mostly quiet day,
shows 0.06 ACU-hours.

Awake, Aurora bills $0.12 per ACU-hour; Oct 13 billed 1.87 ACU-hours for $0.22. At the
0.5–1 ACU these queries use, that is $0.06–0.12 per hour. A visitor's first question
keeps it awake for at least the 30-minute pause window, so a short demo session costs
roughly **$0.03–0.06 for the database plus $0.01–0.03 per question**.

## Limits that cap the bill

- API Gateway throttling: 2 requests/s overall and 1/s on `/query`. Beyond that, the
  account's Lambda concurrency limit applies.
- At most 2 model calls per question, bounded output tokens, and a 500-character
  question limit.
- Aurora is capped at 2 ACU.
- A $20 monthly budget with email alerts, plus alarms on errors, throttles, 5xx and
  model failures ([ADR 0004](adr/0004-public-access-and-cost-controls.md)).
- The access code keeps the site from being a free public LLM endpoint.

## Reproducing the numbers

```python
# AWS_PROFILE=<your profile>; Cost Explorer is a global API served from us-east-1
import boto3
ce = boto3.client("ce", region_name="us-east-1")
ce.get_cost_and_usage(
    TimePeriod={"Start": "2026-10-01", "End": "2026-10-15"},
    Granularity="DAILY",
    Metrics=["UnblendedCost"],
    Filter={"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Usage"]}},  # before credits
    GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
)
```

For this project only, filter by its tag instead of picking services:

```python
Filter={"And": [
    {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Usage"]}},
    {"Tags": {"Key": "Project", "Values": ["olist-nlsql"]}},
]}
```

Bedrock calls aren't tagged resources, so model usage shows up untagged. Count it by
service (Claude Sonnet 4.6), as in the table above.

Token counts per question are in every run record under `eval/results/`
(`input_tokens` there includes cached input).
