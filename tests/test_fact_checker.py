"""Tests for fact checker heuristics."""

from pathlib import Path

from futuredecoded.editorial.fact_checker import verify_story


def test_fact_check_rejects_rumor(tmp_path: Path):
    result = verify_story(
        title="Unconfirmed rumor about secret AI project",
        url="https://example.com",
        output_dir=tmp_path,
    )
    assert result.passed is False
    assert (tmp_path / "fact_check_log.json").exists()


def test_fact_check_passes_valid_story(tmp_path: Path):
    result = verify_story(
        title="OpenAI announces new developer tools",
        url="https://openai.com/blog/new-tools",
        output_dir=tmp_path,
    )
    assert result.passed is True
