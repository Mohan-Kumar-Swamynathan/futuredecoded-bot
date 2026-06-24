"""Tests for section-level visual keyword helpers."""

from futuredecoded.media.visual_keywords import (
    _build_entity_queries,
    _tokenize,
    build_section_search_keywords,
    build_section_visual_prompt,
    score_video_tag_relevance,
)


def test_build_section_visual_prompt_prefers_section_text_over_chatgpt():
    prompt = build_section_visual_prompt(
        "Background",
        "Superhuman acquired GPTZero to strengthen AI detection in email",
        "Superhuman acquires AI detection startup GPTZero",
        visual_style="real_footage",
    )
    assert "chatgpt" not in prompt.lower()
    assert "superhuman" in prompt.lower() or "gptzero" in prompt.lower() or "detection" in prompt.lower()


def test_build_entity_queries_maps_gptzero_without_chatgpt():
    queries = _build_entity_queries(_tokenize("Superhuman acquires AI detection startup GPTZero"))
    joined = " ".join(queries).lower()
    assert "chatgpt" not in joined
    assert "detection" in joined or "gptzero" in joined.replace(" ", "")


def test_build_section_search_keywords_returns_unique_queries():
    keywords = build_section_search_keywords(
        "Background",
        "Amazon met with regulators about Anthropic",
        "Amazon Anthropic Review",
        visual_style="real_footage",
    )
    assert len(keywords) >= 2
    assert len({keyword.lower() for keyword in keywords}) == len(keywords)


def test_score_video_tag_relevance_prefers_matching_tags():
    high = score_video_tag_relevance("nvidia gpu data center", "nvidia gpu server data center")
    low = score_video_tag_relevance("nvidia gpu data center", "beach sunset travel")
    assert high > low
