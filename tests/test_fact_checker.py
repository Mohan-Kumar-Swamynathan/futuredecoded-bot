"""Tests for fact checker source enrichment."""

from pathlib import Path
from unittest.mock import patch

from futuredecoded.editorial.fact_checker import _enrich_sources, verify_story

MOCK_GOOGLE_SOURCES = [
    {
        "name": "Reuters",
        "url": "https://news.google.com/rss/articles/reuters",
        "headline": "Amazon CEO talks with officials",
        "verified": True,
    },
    {
        "name": "Bloomberg",
        "url": "https://news.google.com/rss/articles/bloomberg",
        "headline": "Amazon regulatory meetings reported",
        "verified": True,
    },
]


@patch(
    "futuredecoded.editorial.fact_checker._fetch_google_news_sources",
    return_value=MOCK_GOOGLE_SOURCES,
)
def test_enrich_sources_pads_to_minimum_three(_mock_google):
    sources = _enrich_sources(
        [{"name": "Only one", "url": "https://example.com/story", "verified": True}],
        title="OpenAI announces new tool",
        url="https://example.com/story",
        google_news_sources=MOCK_GOOGLE_SOURCES,
    )
    assert len(sources) >= 3
    assert any(source.get("name") == "Reuters" for source in sources)


@patch(
    "futuredecoded.editorial.fact_checker._fetch_google_news_sources",
    return_value=MOCK_GOOGLE_SOURCES,
)
def test_verify_story_passes_when_llm_returns_single_source(
    _mock_google,
    tmp_path: Path,
    monkeypatch,
):
    class FakeLlm:
        def call_json(self, prompt: str):
            assert "Corroborating Google News coverage" in prompt
            return {
                "passed": True,
                "confidence": 0.8,
                "reason": "Looks credible",
                "sources": [{"name": "Primary", "url": "https://example.com/amazon", "verified": True}],
            }

    monkeypatch.setattr(
        "futuredecoded.editorial.fact_checker.get_llm_client",
        lambda: FakeLlm(),
    )

    result = verify_story(
        title="Amazon CEO talks with officials",
        url="https://example.com/amazon",
        output_dir=tmp_path,
    )
    assert result.passed is True
    assert len(result.sources) >= 3
    assert (tmp_path / "fact_check_log.json").exists()


@patch(
    "futuredecoded.editorial.fact_checker._fetch_google_news_sources",
    return_value=MOCK_GOOGLE_SOURCES,
)
def test_verify_story_rejects_rumor_title(_mock_google, tmp_path: Path, monkeypatch):
    class FakeLlm:
        def call_json(self, prompt: str):
            return {"passed": True, "confidence": 0.9, "reason": "ok", "sources": []}

    monkeypatch.setattr(
        "futuredecoded.editorial.fact_checker.get_llm_client",
        lambda: FakeLlm(),
    )

    result = verify_story(
        title="Unconfirmed rumor about secret AI project",
        url="https://example.com/rumor",
        output_dir=tmp_path,
    )
    assert result.passed is False
