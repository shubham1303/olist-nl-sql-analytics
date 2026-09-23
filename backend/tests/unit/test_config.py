import pytest

from olist_nlsql.config import MAX_RESULT_ROWS_CEILING, ConfigError, Settings, load_settings


def test_defaults_when_env_is_empty() -> None:
    assert load_settings({}) == Settings()


def test_default_model_is_us_sonnet_5_profile() -> None:
    assert load_settings({}).bedrock_model_id == "us.anthropic.claude-sonnet-5"


def test_env_overrides() -> None:
    settings = load_settings(
        {
            "NLSQL_AWS_REGION": "us-west-2",
            "NLSQL_BEDROCK_MODEL_ID": "some.other-model",
            "NLSQL_LLM_MAX_OUTPUT_TOKENS": "1024",
            "NLSQL_MAX_QUESTION_CHARS": "300",
            "NLSQL_MAX_REQUEST_BYTES": "2048",
            "NLSQL_MAX_RESULT_ROWS": "250",
        }
    )
    assert settings == Settings(
        aws_region="us-west-2",
        bedrock_model_id="some.other-model",
        llm_max_output_tokens=1024,
        max_question_chars=300,
        max_request_bytes=2048,
        max_result_rows=250,
    )


def test_unprefixed_variables_are_ignored() -> None:
    assert load_settings({"BEDROCK_MODEL_ID": "ignored"}) == Settings()


@pytest.mark.parametrize("value", ["abc", "1.5", ""])
def test_non_integer_rejected(value: str) -> None:
    with pytest.raises(ConfigError, match="must be an integer"):
        load_settings({"NLSQL_MAX_QUESTION_CHARS": value})


@pytest.mark.parametrize("value", ["0", "-1"])
def test_non_positive_rejected(value: str) -> None:
    with pytest.raises(ConfigError, match="must be positive"):
        load_settings({"NLSQL_LLM_MAX_OUTPUT_TOKENS": value})


def test_result_rows_cannot_exceed_ceiling() -> None:
    with pytest.raises(ConfigError, match="at most"):
        load_settings({"NLSQL_MAX_RESULT_ROWS": str(MAX_RESULT_ROWS_CEILING + 1)})


def test_blank_string_rejected() -> None:
    with pytest.raises(ConfigError, match="must not be empty"):
        load_settings({"NLSQL_BEDROCK_MODEL_ID": "   "})
