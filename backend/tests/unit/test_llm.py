"""Model layer: structured-output parsing, the Bedrock client (SDK mocked), the fake."""

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from olist_nlsql.config import Settings
from olist_nlsql.llm import (
    OUTPUT_SCHEMA,
    ModelError,
    ModelRequest,
    OutputParseError,
    parse_generation,
)
from olist_nlsql.llm.bedrock import BedrockModelClient
from olist_nlsql.llm.fake import FakeModelClient, reply_json

REQUEST = ModelRequest(system="SYSTEM", user="Question: x", output_schema=OUTPUT_SCHEMA)


# parsing


def test_parse_valid_reply() -> None:
    g = parse_generation(
        reply_json(
            "SELECT 1",
            interpretation="One.",
            assumptions=["a", "  "],
            metrics_used=["revenue"],
        )
    )
    assert (g.can_answer, g.sql, g.interpretation) == (True, "SELECT 1", "One.")
    assert g.assumptions == ("a",) and g.metrics_used == ("revenue",)


def test_parse_accepts_an_array_sent_as_json_text() -> None:
    reply = {**json.loads(reply_json("SELECT 1")), "assumptions": '["Best = highest average."]'}
    g = parse_generation(json.dumps(reply))
    assert g.assumptions == ("Best = highest average.",)


def test_parse_error_shows_the_bad_value() -> None:
    reply = {**json.loads(reply_json("SELECT 1")), "metrics_used": "revenue"}
    with pytest.raises(OutputParseError, match='got "revenue"'):
        parse_generation(json.dumps(reply))


def test_parse_unanswerable_reply_drops_sql() -> None:
    g = parse_generation(reply_json("SELECT 1", can_answer=False, interpretation="No names."))
    assert not g.can_answer and g.sql == ""


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "SELECT 1",  # prose/SQL instead of JSON
        "[]",
        json.dumps({"sql": "SELECT 1"}),  # missing keys
        reply_json("SELECT 1")[:-1] + ', "chart": "bar"}',  # extra key
        reply_json(""),  # can_answer true but no SQL
        json.dumps({**json.loads(reply_json("SELECT 1")), "can_answer": "yes"}),
        json.dumps({**json.loads(reply_json("SELECT 1")), "assumptions": "one"}),
        json.dumps({**json.loads(reply_json("SELECT 1")), "assumptions": "[not json"}),
        json.dumps({**json.loads(reply_json("SELECT 1")), "assumptions": "[1, 2]"}),
        json.dumps({**json.loads(reply_json("SELECT 1")), "sql": ["SELECT 1"]}),
        json.dumps({**json.loads(reply_json("SELECT 1")), "interpretation": " "}),
    ],
)
def test_parse_rejects_malformed_replies(text: str) -> None:
    with pytest.raises(OutputParseError):
        parse_generation(text)


def test_output_schema_is_strict() -> None:
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert set(OUTPUT_SCHEMA["required"]) == set(OUTPUT_SCHEMA["properties"])
    assert "chart" not in json.dumps(OUTPUT_SCHEMA)


# bedrock


@dataclass
class _FakeMessages:
    response: Any = None
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _client(messages: _FakeMessages, settings: Settings | None = None) -> BedrockModelClient:
    client = BedrockModelClient(settings or Settings())
    client.__dict__["_client"] = SimpleNamespace(messages=messages)  # replace the SDK client
    return client


def _response(stop_reason: str = "tool_use", answer: dict[str, Any] | None = None) -> Any:
    content: list[Any] = [SimpleNamespace(type="thinking", thinking="")]
    if answer is not None:
        content.append(SimpleNamespace(type="text", text="Here is the answer."))
        content.append(SimpleNamespace(type="tool_use", name="submit_answer", input=answer))
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        model="us.anthropic.claude-sonnet-5",
        usage=SimpleNamespace(
            input_tokens=400,
            output_tokens=300,
            cache_read_input_tokens=5600,
            cache_creation_input_tokens=None,
        ),
    )


ANSWER = json.loads(reply_json("SELECT 1"))


def test_client_targets_bedrock_runtime_not_mantle() -> None:
    from anthropic import AnthropicBedrock

    sdk = BedrockModelClient(Settings())._client
    assert isinstance(sdk, AnthropicBedrock)
    assert str(sdk.base_url).startswith("https://bedrock-runtime.us-east-1.amazonaws.com")


def test_request_forces_the_answer_tool_with_thinking_disabled() -> None:
    settings = Settings(bedrock_model_id="us.anthropic.some-model", llm_effort="low")
    params = BedrockModelClient(settings).request_params(REQUEST)
    assert params["model"] == "us.anthropic.some-model"
    assert params["max_tokens"] == settings.llm_max_output_tokens
    assert params["tools"][0]["name"] == "submit_answer"
    assert params["tools"][0]["input_schema"] == OUTPUT_SCHEMA
    assert params["tool_choice"] == {"type": "tool", "name": "submit_answer"}
    # Bedrock + Claude Sonnet 5: a forced tool call requires thinking disabled.
    assert params["thinking"] == {"type": "disabled"}
    assert params["system"] == [
        {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    ]
    assert params["messages"] == [{"role": "user", "content": "Question: x"}]
    assert params["output_config"] == {"effort": "low"}
    # Structured outputs are unsupported for Sonnet 5 on Bedrock; sampling params are rejected.
    assert "format" not in params["output_config"]
    assert "temperature" not in params


def test_adaptive_thinking_asks_for_the_tool_instead_of_forcing_it() -> None:
    params = BedrockModelClient(Settings(llm_thinking="adaptive")).request_params(REQUEST)
    assert params["tool_choice"] == {"type": "auto"}
    assert params["thinking"] == {"type": "adaptive"}


def test_reply_is_the_tool_input_and_reports_usage() -> None:
    messages = _FakeMessages(response=_response(answer=ANSWER))
    reply = _client(messages).complete(REQUEST)
    assert json.loads(reply.text) == ANSWER
    assert parse_generation(reply.text).sql == "SELECT 1"
    assert (reply.input_tokens, reply.output_tokens) == (400, 300)
    assert (reply.cache_read_tokens, reply.cache_write_tokens) == (5600, 0)
    assert len(messages.calls) == 1


@pytest.mark.parametrize(
    ("stop_reason", "answer", "kind"),
    [
        ("refusal", ANSWER, "refused"),
        ("max_tokens", ANSWER, "truncated"),
        ("end_turn", None, "empty"),  # no submit_answer call
    ],
)
def test_bad_replies_become_model_errors(
    stop_reason: str, answer: dict[str, Any] | None, kind: str
) -> None:
    with pytest.raises(ModelError) as info:
        _client(_FakeMessages(response=_response(stop_reason, answer))).complete(REQUEST)
    assert info.value.kind == kind


_REQ = httpx2.Request("POST", "https://bedrock-runtime.us-east-1.amazonaws.com")


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (anthropic.PermissionDeniedError("x", response=httpx2.Response(403, request=_REQ), body={"error": {"message": "model not available for this account"}}), "access_denied"),
        (anthropic.NotFoundError("x", response=httpx2.Response(404, request=_REQ), body=None), "model_not_found"),
        (anthropic.RateLimitError("x", response=httpx2.Response(429, request=_REQ), body=None), "throttled"),
        (anthropic.InternalServerError("x", response=httpx2.Response(500, request=_REQ), body=None), "api_error"),
        (anthropic.APITimeoutError(request=_REQ), "timeout"),
        (anthropic.APIConnectionError(request=_REQ), "connection"),
    ],
)  # fmt: skip
def test_sdk_errors_are_mapped(error: Exception, kind: str) -> None:
    with pytest.raises(ModelError) as info:
        _client(_FakeMessages(error=error)).complete(REQUEST)
    assert info.value.kind == kind
    assert info.value.__cause__ is None  # no SDK traceback chained into results


def test_access_denied_message_is_passed_through() -> None:
    error = anthropic.PermissionDeniedError(
        "x",
        response=httpx2.Response(403, request=_REQ),
        body={"error": {"message": "anthropic.claude-sonnet-5 is not available for this account."}},
    )
    with pytest.raises(ModelError, match="not available for this account"):
        _client(_FakeMessages(error=error)).complete(REQUEST)


def test_model_id_only_from_settings() -> None:
    assert BedrockModelClient(Settings()).model_id == Settings().bedrock_model_id


# fake


def test_fake_fails_loudly_on_an_unscripted_call() -> None:
    fake = FakeModelClient.of(reply_json("SELECT 1"))
    fake.complete(REQUEST)
    with pytest.raises(AssertionError, match="unexpected model call #2"):
        fake.complete(REQUEST)
