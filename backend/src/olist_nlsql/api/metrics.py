"""CloudWatch metrics as Embedded Metric Format log lines (no SDK calls, no extra latency).

One JSON line per request on stdout. CloudWatch Logs turns the ``_aws`` block into
metrics in the ``OlistNlSql`` namespace; the other keys stay searchable in Logs
Insights. Dimensions are kept small: Route, and Route x Outcome (a pipeline status,
a database state, or an error code), so the number of metric series stays bounded.
"""

import json
import time
from collections.abc import Mapping
from typing import Any

NAMESPACE = "OlistNlSql"

# observation key -> (metric name, unit)
_METRICS: dict[str, tuple[str, str]] = {
    "total_ms": ("LatencyMs", "Milliseconds"),
    "model_ms": ("ModelMs", "Milliseconds"),
    "execution_ms": ("ExecutionMs", "Milliseconds"),
    "model_calls": ("ModelCalls", "Count"),
    "input_tokens": ("InputTokens", "Count"),
    "output_tokens": ("OutputTokens", "Count"),
}


def emf_record(
    observation: Mapping[str, Any],
    http_status: int,
    duration_ms: float,
    *,
    now_ms: int | None = None,
) -> dict[str, Any]:
    route = str(observation.get("route", "other"))
    outcome = str(observation.get("outcome", "unknown"))
    values: dict[str, float] = {"Requests": 1, "HandlerMs": round(duration_ms, 2)}
    units = {"Requests": "Count", "HandlerMs": "Milliseconds"}
    for key, (name, unit) in _METRICS.items():
        value = observation.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values[name] = value
            units[name] = unit
    if observation.get("repair_attempted"):
        values["Repairs"] = 1
        units["Repairs"] = "Count"
    return {
        "_aws": {
            "Timestamp": now_ms if now_ms is not None else int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [["Route"], ["Route", "Outcome"]],
                    "Metrics": [{"Name": n, "Unit": units[n]} for n in values],
                }
            ],
        },
        "event": "nlsql_request",
        "Route": route,
        "Outcome": outcome,
        "http_status": http_status,
        **values,
    }


def emit(record: Mapping[str, Any]) -> None:
    print(json.dumps(record, separators=(",", ":")), flush=True)
