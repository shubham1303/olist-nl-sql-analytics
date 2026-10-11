"""Claude on Amazon Bedrock: the bedrock-runtime endpoint, Messages request shape (ADR 0016).

``anthropic.AnthropicBedrock`` sends the Anthropic Messages body to bedrock-runtime's
InvokeModel API (``POST https://bedrock-runtime.{region}.amazonaws.com/model/{id}/invoke``),
signed with the normal AWS credential chain (AWS_PROFILE, SSO, env vars, or the
Lambda role). AWS creds deliberately don't come from .env.

Structured output: JSON-schema structured outputs (``output_config.format``) are not
supported for Claude Sonnet 5 on Bedrock, so the reply is a single call to the
``submit_answer`` tool whose ``input_schema`` is the output schema. The strict parser
in ``output.py`` re-checks it.
"""

import json
from functools import cached_property
from typing import Any

import anthropic
from anthropic import AnthropicBedrock

from olist_nlsql.config import Settings
from olist_nlsql.llm.client import ModelError, ModelReply, ModelRequest

ANSWER_TOOL = "submit_answer"

# One transport retry for connection errors and 5xx/429: bounded latency (ADR 0004).
_TRANSPORT_RETRIES = 1


class BedrockModelClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model_id(self) -> str:
        return self._settings.bedrock_model_id

    @cached_property
    def _client(self) -> AnthropicBedrock:
        return AnthropicBedrock(
            aws_region=self._settings.aws_region,
            timeout=float(self._settings.llm_timeout_seconds),
            max_retries=_TRANSPORT_RETRIES,
        )

    def request_params(self, request: ModelRequest) -> dict[str, Any]:
        """Request body. Public so tests and --show-prompt can look at it."""
        forced = self._settings.llm_thinking == "disabled"
        return {
            "model": self.model_id,
            "max_tokens": self._settings.llm_max_output_tokens,
            "tools": [
                {
                    "name": ANSWER_TOOL,
                    "description": "Submit the answer to the question. Call exactly once.",
                    "input_schema": request.output_schema,
                }
            ],
            # On Bedrock, Claude Sonnet 5 accepts a forced tool call only with thinking
            # disabled; with adaptive thinking the prompt asks for the call instead.
            "tool_choice": {"type": "tool", "name": ANSWER_TOOL} if forced else {"type": "auto"},
            # The catalog prompt is identical on every call: cache it (explicit breakpoint).
            "system": [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": request.user}],
            "thinking": {"type": self._settings.llm_thinking},
            "output_config": {"effort": self._settings.llm_effort},
        }

    def complete(self, request: ModelRequest) -> ModelReply:
        try:
            response = self._client.messages.create(**self.request_params(request))
        except anthropic.PermissionDeniedError as exc:
            raise ModelError("access_denied", _message(exc)) from None
        except anthropic.NotFoundError as exc:
            raise ModelError("model_not_found", _message(exc)) from None
        except anthropic.RateLimitError as exc:
            raise ModelError("throttled", _message(exc)) from None
        except anthropic.APITimeoutError:
            raise ModelError("timeout", "the Bedrock request timed out") from None
        except anthropic.APIConnectionError:
            raise ModelError("connection", "could not connect to Bedrock") from None
        except anthropic.APIStatusError as exc:
            raise ModelError("api_error", f"HTTP {exc.status_code}: {_message(exc)}") from None

        if response.stop_reason == "refusal":
            raise ModelError("refused", "the model declined to answer")
        if response.stop_reason == "max_tokens":
            raise ModelError("truncated", "the reply hit the output token limit")
        answer = next(
            (b.input for b in response.content if b.type == "tool_use" and b.name == ANSWER_TOOL),
            None,
        )
        if answer is None:
            raise ModelError("empty", f"the reply did not call {ANSWER_TOOL}")
        return ModelReply(
            text=json.dumps(answer),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", None) or 0,
            cache_write_tokens=getattr(response.usage, "cache_creation_input_tokens", None) or 0,
        )


def _message(exc: anthropic.APIStatusError) -> str:
    body = exc.body
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return str(error["message"])[:300]
        if isinstance(body.get("message"), str):  # bedrock-runtime error shape
            return str(body["message"])[:300]
    return str(exc.message)[:300]
