"""Application settings, read from environment variables.

This module is the only place defaults live, including the Bedrock model ID
(see docs/adr/0003). Everything else receives a ``Settings`` instance.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

ENV_PREFIX = "NLSQL_"

# Hard ceiling from ADR 0004: keeps Data API responses well under its 1 MiB cap.
MAX_RESULT_ROWS_CEILING = 1000

Effort = Literal["low", "medium", "high", "xhigh", "max"]
EFFORTS: tuple[Effort, ...] = ("low", "medium", "high", "xhigh", "max")
Thinking = Literal["adaptive", "disabled"]
THINKING_MODES: tuple[Thinking, ...] = ("adaptive", "disabled")


class ConfigError(ValueError):
    """Raised when an environment variable holds an invalid value."""


@dataclass(frozen=True, slots=True)
class Settings:
    aws_region: str = "us-east-1"
    # bedrock-runtime US geo inference profile (ADR 0016). Sonnet 5 on bedrock-runtime
    # requires a geo (us./eu./au.) or global. ID; the bare model ID is not accepted.
    bedrock_model_id: str = "us.anthropic.claude-sonnet-5"
    # Output cap per model call, thinking included (ADR 0003, 0004).
    llm_max_output_tokens: int = 4096
    llm_effort: Effort = "medium"
    # "disabled" forces the submit_answer tool call (required for a forced tool call on
    # Bedrock); "adaptive" lets the model think and asks for the call in the prompt.
    llm_thinking: Thinking = "disabled"
    llm_timeout_seconds: int = 60
    max_question_chars: int = 500
    max_request_bytes: int = 4096
    max_result_rows: int = MAX_RESULT_ROWS_CEILING
    # SQL validator limits (docs/sql-safety.md).
    max_sql_chars: int = 8000
    max_joins: int = 6


def _read_str(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(ENV_PREFIX + name, default).strip()
    if not value:
        raise ConfigError(f"{ENV_PREFIX}{name} must not be empty")
    return value


def _read_int(
    env: Mapping[str, str], name: str, default: int, *, maximum: int | None = None
) -> int:
    raw = env.get(ENV_PREFIX + name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{ENV_PREFIX}{name} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{ENV_PREFIX}{name} must be positive, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{ENV_PREFIX}{name} must be at most {maximum}, got {value}")
    return value


def _read_choice(env: Mapping[str, str], name: str, default: str, choices: tuple[str, ...]) -> str:
    value = _read_str(env, name, default)
    if value not in choices:
        raise ConfigError(f"{ENV_PREFIX}{name} must be one of {', '.join(choices)}, got {value!r}")
    return value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build ``Settings`` from ``env`` (defaults to ``os.environ``)."""
    env = os.environ if env is None else env
    defaults = Settings()
    return Settings(
        aws_region=_read_str(env, "AWS_REGION", defaults.aws_region),
        bedrock_model_id=_read_str(env, "BEDROCK_MODEL_ID", defaults.bedrock_model_id),
        llm_max_output_tokens=_read_int(
            env, "LLM_MAX_OUTPUT_TOKENS", defaults.llm_max_output_tokens
        ),
        llm_effort=cast(Effort, _read_choice(env, "LLM_EFFORT", defaults.llm_effort, EFFORTS)),
        llm_thinking=cast(
            Thinking, _read_choice(env, "LLM_THINKING", defaults.llm_thinking, THINKING_MODES)
        ),
        llm_timeout_seconds=_read_int(env, "LLM_TIMEOUT_SECONDS", defaults.llm_timeout_seconds),
        max_question_chars=_read_int(env, "MAX_QUESTION_CHARS", defaults.max_question_chars),
        max_request_bytes=_read_int(env, "MAX_REQUEST_BYTES", defaults.max_request_bytes),
        max_result_rows=_read_int(
            env, "MAX_RESULT_ROWS", defaults.max_result_rows, maximum=MAX_RESULT_ROWS_CEILING
        ),
        max_sql_chars=_read_int(env, "MAX_SQL_CHARS", defaults.max_sql_chars),
        max_joins=_read_int(env, "MAX_JOINS", defaults.max_joins),
    )
