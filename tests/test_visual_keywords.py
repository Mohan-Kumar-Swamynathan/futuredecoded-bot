"""Tests for story-relevant visual keyword builder."""

from futuredecoded.media.visual_keywords import build_visual_search_queries, score_image_relevance


def test_build_visual_search_queries_includes_story_phrase():
    queries = build_visual_search_queries(
        "Amazon CEO talks with U.S. officials triggered crackdown on Anthropic AI",
        outline={"key_facts": ["Regulators reviewed Anthropic AI models"]},
        sections=[{"label": "Background", "text": "Amazon leadership met government officials"}],
    )
    assert any("amazon" in query.lower() for query in queries)
    assert any("anthropic" in query.lower() or "artificial intelligence" in query.lower() for query in queries)


def test_score_image_relevance_prefers_matching_alt_text():
    high = score_image_relevance(
        "Amazon CEO talks with officials",
        "Amazon executive meeting in corporate office",
        "Amazon CEO business meeting",
    )
    low = score_image_relevance(
        "Amazon CEO talks with officials",
        "Mountain landscape at sunset",
        "nature photography",
    )
    assert high > low
