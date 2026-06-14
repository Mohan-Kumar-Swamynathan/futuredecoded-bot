"""Tests for fact checker source enrichment."""

from pathlib import Path

from futuredecoded.editorial.fact_checker import _enrich_sources, verify_story


def test_enrich_sources_pads_to_minimum_three():
    sources = _enrich_sources(
        [{"name": "Only one", "url": "https://example.com/story", "verified": True}],
        title="OpenAI announces new tool",
        url="https://example.com/story",
    )
    assert len(sources) >= 3


def test_verify_story_passes_when_llm_returns_single_source(tmp_path: Path, monkeypatch):
    class FakeLlm:
        def call_json(self, prompt: str):
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


def test_verify_story_rejects_rumor_title(tmp_path: Path, monkeypatch):
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
