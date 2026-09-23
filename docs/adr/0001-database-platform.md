# 0001. Database platform: Aurora Serverless v2 + RDS Data API, Docker Postgres locally

- Status: Accepted
- Date: 2026-09-23

## Context

The workload is read-only analytics over a static dataset of roughly 100k orders, with
bursty, low-volume traffic. We need a real PostgreSQL engine (LLMs write the Postgres
dialect well), a low idle cost, and a Lambda backend that doesn't require VPC
networking (NAT, VPC endpoints, RDS Proxy).

## Decision

- **AWS:** Aurora Serverless v2 PostgreSQL, accessed only through the **RDS Data API**.
  Auto-pause is enabled (minimum 0 ACU), with a small maximum ACU (starting at 2).
  Cluster in private subnets. No public access.
- **Local:** Docker PostgreSQL (the same major version as Aurora), accessed with a
  normal driver (psycopg).
- **Abstraction:** the application depends on a `QueryExecutor` protocol with two
  implementations, `PostgresExecutor` (local) and `DataApiExecutor` (AWS). A shared
  contract test suite runs against both and pins type normalisation (decimals,
  timestamps, nulls), empty results and truncation.
- **Bulk load (AWS):** CSVs are uploaded to S3 and imported with the Aurora `aws_s3`
  extension (`aws_s3.table_import_from_s3`). The cluster has an IAM role and reaches S3
  through an S3 gateway VPC endpoint, which is free. The Data API is not used for bulk
  inserts.
- **Auto-pause handling:** a lightweight, authenticated `GET /status` endpoint reports
  database readiness and triggers a resume. The Data API executor retries
  `DatabaseResumingException` with bounded backoff. The UI shows
  "Starting analytics database..." until the database is ready.

## Consequences

- Lambda stays outside the VPC. No NAT gateway, Bedrock VPC endpoint, RDS Proxy or
  connection pool is needed, and there are no native DB drivers in the Lambda package.
- A cold resume can take longer than a normal request. The API Gateway integration
  timeout is 30 s, so the status/warm-up flow is required, not optional.
- Data API limits apply: a 1 MiB response cap and its own type mapping. Row and column
  limits keep responses well under the cap, and the contract tests catch type drift.
- The two executors can diverge. The contract suite is the guard.
