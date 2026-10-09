"""The narrow model interface the pipeline depends on (ADR 0003, ADR 0016).

One request in, one reply out. The pipeline, not the client, decides how many calls
are made; clients never retry at the application level.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

ModelErrorKind = Literal[
    "access_denied",  # credentials or model access (e.g. Bedrock agreement not accepted)
    "model_not_found",
    "throttled",
    "timeout",
    "connection",
    "refused",  # stop_reason "refusal"
    "truncated",  # stop_reason "max_tokens"
    "empty",  # model didn't call submit_answer
    "api_error",
]


@dataclass(frozen=True, slots=True)
class ModelRequest:
    system: str  # the catalog prompt: identical for every call, so it caches
    user: str  # the question, or the repair instruction
    output_schema: dict[str, Any]  # JSON schema the reply must follow


@dataclass(frozen=True, slots=True)
class ModelReply:
    text: str  # the JSON document produced under the output schema
    model: str
    input_tokens: int  # uncached input only
    output_tokens: int
    cache_read_tokens: int = 0  # input served from the prompt cache
    cache_write_tokens: int = 0  # input written to the prompt cache


class ModelError(Exception):
    """Raised when the model call fails. Callers branch on ``kind``."""

    def __init__(self, kind: ModelErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind: ModelErrorKind = kind


class ModelClient(Protocol):
    @property
    def model_id(self) -> str: ...

    def complete(self, request: ModelRequest) -> ModelReply: ...
