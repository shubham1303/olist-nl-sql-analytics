"""The structured reply the model must return, and its strict application-side parser.

The schema is the ``input_schema`` of the ``submit_answer`` tool (llm/bedrock.py).
Bedrock doesn't support structured outputs for Sonnet 5 yet, so nothing actually
enforces the schema on their side. This parser is the real check.
"""

import json
from dataclasses import dataclass
from typing import Any

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["can_answer", "interpretation", "sql", "assumptions", "metrics_used"],
    "properties": {
        "can_answer": {
            "type": "boolean",
            "description": "False when the question cannot be answered from the listed relations.",
        },
        "interpretation": {
            "type": "string",
            "description": "One sentence restating the question exactly as the SQL answers it.",
        },
        "sql": {
            "type": "string",
            "description": "Exactly one PostgreSQL SELECT; empty when can_answer is false.",
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Assumptions made for terms the catalog does not define.",
        },
        "metrics_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Names of catalog metrics the SQL computes.",
        },
    },
}

_KEYS = frozenset(OUTPUT_SCHEMA["required"])


class OutputParseError(ValueError):
    """The model reply does not match the output schema."""


@dataclass(frozen=True, slots=True)
class Generation:
    can_answer: bool
    interpretation: str
    sql: str
    assumptions: tuple[str, ...]
    metrics_used: tuple[str, ...]


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise OutputParseError(f"{field} must be a list of strings")
    return tuple(v.strip() for v in value if v.strip())


def parse_generation(text: str) -> Generation:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OutputParseError(f"reply is not valid JSON ({exc.msg})") from None
    if not isinstance(data, dict):
        raise OutputParseError("reply must be a JSON object")
    if set(data) != _KEYS:
        missing, extra = sorted(_KEYS - set(data)), sorted(set(data) - _KEYS)
        raise OutputParseError(
            f"reply keys differ from the schema (missing {missing}, extra {extra})"
        )
    can_answer, interpretation, sql = data["can_answer"], data["interpretation"], data["sql"]
    if not isinstance(can_answer, bool):
        raise OutputParseError("can_answer must be a boolean")
    if not isinstance(interpretation, str) or not interpretation.strip():
        raise OutputParseError("interpretation must be a non-empty string")
    if not isinstance(sql, str):
        raise OutputParseError("sql must be a string")
    if can_answer and not sql.strip():
        raise OutputParseError("sql is empty although can_answer is true")
    return Generation(
        can_answer=can_answer,
        interpretation=interpretation.strip(),
        sql=sql.strip() if can_answer else "",
        assumptions=_strings(data["assumptions"], "assumptions"),
        metrics_used=_strings(data["metrics_used"], "metrics_used"),
    )
