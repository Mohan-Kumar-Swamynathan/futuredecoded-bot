"""Tests for script generator retry and expansion."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from futuredecoded.editorial.script_generator import generate_scripts


def _short_llm_response():
    return {
        "outline": {"hook": "test"},
        "script_sections": [{"label": "Hook", "text": "short hook only"}],
        "script_short_sections": [{"label": "Hook", "text": "Short hook"}],
        "script_short": "Short hook for Shorts.",
        "script_long": " ".join(["word"] * 130),
    }


def _long_llm_response():
    return {
        "outline": {"hook": "test"},
        "script_sections": [{"label": "Hook", "text": " ".join(["analysis"] * 120)}],
        "script_short_sections": [{"label": "Hook", "text": "Short hook"}],
        "script_short": "Short hook for Shorts.",
        "script_long": " ".join(["word"] * 650),
    }


@patch("futuredecoded.editorial.script_generator.get_llm_client")
def test_generate_scripts_retries_when_long_script_is_too_short(mock_get_llm, tmp_path: Path):
    llm = MagicMock()
    llm.call_json.side_effect = [_short_llm_response(), _long_llm_response()]
    mock_get_llm.return_value = llm

    scripts = generate_scripts("Anthropic safety update", "https://example.com", tmp_path)

    assert len(scripts.script_long.split()) >= 400
    assert llm.call_json.call_count == 2


@patch("futuredecoded.editorial.script_generator.get_llm_client")
def test_generate_scripts_expands_after_failed_retries(mock_get_llm, tmp_path: Path):
    llm = MagicMock()
    llm.call_json.side_effect = [
        _short_llm_response(),
        _short_llm_response(),
        {"script_sections": [{"label": "Hook", "text": " ".join(["word"] * 500)}], "script_long": " ".join(["word"] * 650)},
    ]
    mock_get_llm.return_value = llm

    scripts = generate_scripts("AI regulation news", "https://example.com", tmp_path)

    assert len(scripts.script_long.split()) >= 400
    assert llm.call_json.call_count == 3
