# 0004. Shared access code, throttling, request limits, $20 budget

- Status: Accepted
- Date: 2026-09-23

## Context

This is a public portfolio demo, and every query costs Bedrock tokens and database
time. Full user management (Cognito) is more than the MVP needs. The frontend can't be
trusted to enforce anything.

## Decision

**Access:**
- A single shared access code, sent as the `X-Access-Code` header on every
  `/query` and `/status` request.
- The server stores only a SHA-256 hash (`ACCESS_CODE_SHA256`) and compares it in
  constant time. The plaintext code is never in the frontend bundle, Terraform state or
  logs.
- Users type the code into the UI, and it's kept in `sessionStorage`.
- Rotating the code means changing the hash and redeploying.

**Server-side limits** (all enforced in the Lambda, independent of the UI):

| Limit | Initial value |
|---|---|
| Maximum question length | 500 characters, non-empty after trimming |
| Maximum request body | 4 KiB. JSON only, schema-validated, unknown fields rejected |
| Model calls per question | 2 (generation + one repair) |
| Output tokens per model call | Capped |
| Result rows | 1,000 |
| Result columns | Capped |
| Statement timeout | 10 s |

**Infrastructure limits:**
- API Gateway route throttling on `/query` and `/status`, starting low (a few
  requests per second, small burst).
- Lambda reserved concurrency as a hard ceiling on parallel spend.

**Budget:**
- An AWS Budget of **$20/month** with notifications at 50%, 80% and 100% (actual), plus
  a forecasted 100% alert.
- **The budget is an alert, not a spending cap.** The throttles and limits above are
  the actual cost controls.

## Consequences

- A leaked code allows usage up to the throttle limits, and nothing more. Rotation is
  cheap.
- The access code isn't user identity. There are no per-user quotas in the MVP.
- Limits are configuration values. We'll tune them from CloudWatch data, not guesses.
