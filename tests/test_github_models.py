"""Tests for GitHub Models LLM provider."""

from unittest.mock import MagicMock, patch

import pytest

from futuredecoded.llm.provider_client import ProviderClient


def test_build_chain_includes_github_models_when_token_set(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    client = ProviderClient(
        gemini_key="gemini-key",
        groq_key="groq-key",
        github_models_token="ghp_test_token",
    )
    assert client._providers.index("github_models") > client._providers.index("groq")
    assert client._providers.index("gemini") < client._providers.index("github_models")


def test_build_chain_prioritizes_github_models_in_ci(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = ProviderClient(
        gemini_key="gemini-key",
        groq_key="groq-key",
        github_models_token="ghp_test_token",
    )
    assert client._providers[0] == "github_models"
    assert "gemini" in client._providers
    assert "groq" in client._providers


def test_build_chain_skips_github_models_without_token():
    client = ProviderClient(gemini_key="gemini-key", groq_key="groq-key")
    assert "github_models" not in client._providers


def test_build_chain_uses_github_token_env(monkeypatch):
    monkeypatch.delenv("GITHUB_MODELS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "actions-token")
    client = ProviderClient(gemini_key="gemini-key")
    assert "github_models" in client._providers


@patch("futuredecoded.llm.provider_client.requests.post")
def test_call_github_models_sends_correct_request(mock_post: MagicMock):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"passed": true}'}}]
    }
    mock_post.return_value = mock_response

    client = ProviderClient(github_models_token="ghp_test")
    result = client._call_github_models('{"task": "test"} Respond ONLY with valid JSON.', 512)

    assert result == '{"passed": true}'
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer ghp_test"
    assert call_kwargs["json"]["model"] == "openai/gpt-4.1"
    assert call_kwargs["json"]["response_format"] == {"type": "json_object"}
    assert mock_post.call_args.args[0] == "https://models.github.ai/inference/chat/completions"


@patch("futuredecoded.llm.provider_client.requests.post")
def test_call_github_models_plain_text_omits_json_format(mock_post: MagicMock):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}}]
    }
    mock_post.return_value = mock_response

    client = ProviderClient(github_models_token="ghp_test")
    result = client._call_github_models("Write a short headline.", 256)

    assert result == "Hello world"
    assert "response_format" not in mock_post.call_args.kwargs["json"]
