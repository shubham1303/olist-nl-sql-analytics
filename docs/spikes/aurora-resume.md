# Spike: Aurora Serverless v2 resume through the RDS Data API

- Date: 2026-10-11 (start of Phase 6)
- Question: when the cluster is auto-paused at 0 ACU, how long until a Data API query
  succeeds? Does a call block while the cluster resumes, or fail fast? Does either fit
  inside API Gateway's 30 s integration timeout?
- Raw data: [aurora-resume-2026-10-11.jsonl](aurora-resume-2026-10-11.jsonl).
- Script: [aurora_resume_spike.py](aurora_resume_spike.py).

## Setup

Throwaway cluster `olist-resume-spike`, created with the CLI (not Terraform) in
us-east-1:
- Aurora PostgreSQL 16.15, one `db.serverless` writer.
- 0–1 ACU, auto-pause after 300 s idle.
- Data API on, RDS-managed master secret, no public access, default VPC.
- Query: `SELECT count(*) FROM pg_class` through `rds-data execute-statement`.

Each trial:
1. Waited until CloudWatch reported a full minute at 0 ACU that started after the
   previous call (`ServerlessDatabaseCapacity`). The first batch skipped this check for
   trials 2–5 by mistake; those ran against an awake instance and are discarded.
2. Called the Data API once a second until a call succeeded.

## Results (5 valid trials, paused for about 1.5 min each)

| Measure | Values (s) | Summary |
|---|---|---|
| First call → `DatabaseResumingException` | 2.95, 3.99, 3.41, 4.23, 2.91 | Fails fast; never blocked |
| Longest single call during resume | — | 6.1 s |
| First call → first success (incl. 1 s waits) | 16.1, 20.3, 18.9, 19.1, 16.9 | Mean 18.2, max 20.3 |
| Calls until success | 4, 5, 5, 5, 5 | — |
| Warm call right after | 0.18, 0.07, 0.03, 0.08, 0.09 | Under 0.2 s |

This matches AWS's documented typical resume of about 15 s.

## What it means for the design

- **The `/status` warm-up flow works as planned.** A Data API call against a paused
  cluster returns `DatabaseResumingException` within about 4 s (6 s at worst), so a
  `/status` Lambda can call once, map that error to `{"db": "resuming"}`, and return
  well inside 30 s.
  - The UI polls every few seconds. It should expect "Starting analytics database…" for
    about 15–20 s, and up to about 30 s+ after a long pause (see below).
- **`/query` must not wait for a resume inside the request.** About 20 s of resume, plus
  one or two Bedrock calls (about 2–6 s), plus the query would leave little margin
  under 30 s, and none after a deep sleep.
  - On `DatabaseResumingException`, `/query` returns a typed "resuming" error. The UI
    shows the starting state and retries, or goes through `/status` first.
- The executor needs one more error kind ("resuming") so this case is not reported as a
  generic execution failure.

## Not yet measured

**Deep sleep.** AWS says an instance paused for more than 24 hours can take 30 s or
more to resume. That trial needs the cluster to stay paused for about a day; maintenance
can wake it early. The cluster was left paused for this; storage and the secret cost
cents per day.

## Cost

Well under $1. Setup and the trials kept the instance awake for about an hour at
no more than 1 ACU. Paused time is billed for storage only.
