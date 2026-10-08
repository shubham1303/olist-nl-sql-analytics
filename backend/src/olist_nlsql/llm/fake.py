"""Fake model for tests and for running the CLI offline (--fake-sql)."""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from olist_nlsql.llm.client import ModelError, ModelReply, ModelRequest


def reply_json(
    sql: str,
    *,
    interpretation: str = "Answer the question as asked.",
    assumptions: Sequence[str] = (),
    metrics_used: Sequence[str] = (),
    can_answer: bool = True,
) -> str:
    """Build a reply shaped like the real model's submit_answer output."""
    return json.dumps(
        {
            "can_answer": can_answer,
            "interpretation": interpretation,
            "sql": sql,
            "assumptions": list(assumptions),
            "metrics_used": list(metrics_used),
        }
    )


@dataclass
class FakeModelClient:
    """Returns scripted replies in order. Raises if called more times than scripted,
    so a test fails loudly if the pipeline ever makes an unexpected extra call."""

    replies: list[str | ModelError]
    model_id: str = "fake-model"
    requests: list[ModelRequest] = field(default_factory=list)

    @classmethod
    def of(cls, *replies: str | ModelError) -> "FakeModelClient":
        return cls(list(replies))

    def complete(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        if len(self.requests) > len(self.replies):
            raise AssertionError(f"unexpected model call #{len(self.requests)}")
        reply = self.replies[len(self.requests) - 1]
        if isinstance(reply, ModelError):
            raise reply
        return ModelReply(text=reply, model=self.model_id, input_tokens=0, output_tokens=0)

    def sent_text(self) -> Iterable[str]:
        for request in self.requests:
            yield request.system
            yield request.user
