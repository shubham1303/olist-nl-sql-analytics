"""Aurora Serverless v2 resume spike: time RDS Data API calls against a paused cluster.

usage: SPIKE_CLUSTER_ARN=... SPIKE_SECRET_ARN=... SPIKE_INSTANCE=...        python aurora_resume_spike.py TRIALS        (one JSON line per trial on stdout)

Each trial waits for a CloudWatch minute at 0 ACU that starts after the previous call,
then calls the Data API once a second until a call succeeds. See aurora-resume.md.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

CLUSTER_ARN = os.environ["SPIKE_CLUSTER_ARN"]
SECRET_ARN = os.environ["SPIKE_SECRET_ARN"]
INSTANCE = os.environ.get("SPIKE_INSTANCE", "olist-resume-spike-1")
SQL = "SELECT count(*) FROM pg_class"

cw = boto3.client("cloudwatch", region_name="us-east-1")
data = boto3.client(
    "rds-data",
    region_name="us-east-1",
    config=Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 1}),
)


def log(msg: str) -> None:
    print(f"# {datetime.now(UTC).isoformat(timespec='seconds')} {msg}", file=sys.stderr, flush=True)


def latest_capacity() -> tuple[datetime, float] | None:
    now = datetime.now(UTC)
    points = cw.get_metric_statistics(
        Namespace="AWS/RDS",
        MetricName="ServerlessDatabaseCapacity",
        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": INSTANCE}],
        StartTime=now - timedelta(minutes=5),
        EndTime=now,
        Period=60,
        Statistics=["Maximum"],
    )["Datapoints"]
    if not points:
        return None
    p = max(points, key=lambda d: d["Timestamp"])
    return p["Timestamp"], float(p["Maximum"])


def wait_paused(after: datetime, limit_s: int = 2400) -> datetime:
    """Block until a minute at 0 ACU is reported that starts after ``after``."""
    start = time.monotonic()
    while time.monotonic() - start < limit_s:
        cap = latest_capacity()
        if cap and cap[1] == 0.0 and cap[0] > after:
            log(f"paused (capacity 0 at {cap[0].isoformat()})")
            return cap[0]
        time.sleep(30)
    raise TimeoutError("instance did not pause")


def call() -> tuple[float, str]:
    t0 = time.monotonic()
    try:
        data.execute_statement(
            resourceArn=CLUSTER_ARN, secretArn=SECRET_ARN, database="postgres", sql=SQL
        )
        return time.monotonic() - t0, "ok"
    except ClientError as exc:
        return time.monotonic() - t0, exc.response["Error"]["Code"]
    except BotoCoreError as exc:
        return time.monotonic() - t0, type(exc).__name__


def trial(n: int, last_activity: datetime) -> dict[str, object]:
    paused_at = wait_paused(after=last_activity)
    started = time.monotonic()
    calls = []
    while True:
        elapsed, outcome = call()
        calls.append({"at_s": round(time.monotonic() - started - elapsed, 2), "took_s": round(elapsed, 2), "outcome": outcome})
        if outcome == "ok" or time.monotonic() - started > 180:
            break
        time.sleep(1)
    warm_s, warm_outcome = call()
    return {
        "trial": n,
        "paused_for_min": round((datetime.now(UTC) - paused_at).total_seconds() / 60, 1),
        "first_call_s": calls[0]["took_s"],
        "first_call_outcome": calls[0]["outcome"],
        "calls": len(calls),
        "time_to_first_success_s": round(time.monotonic() - started - warm_s, 2)
        if calls[-1]["outcome"] == "ok"
        else None,
        "warm_call_s": round(warm_s, 2),
        "warm_outcome": warm_outcome,
        "call_log": calls,
    }


if __name__ == "__main__":
    last = datetime.now(UTC)
    for n in range(1, int(sys.argv[1]) + 1):
        result = trial(n, last)
        last = datetime.now(UTC)
        print(json.dumps(result), flush=True)
