"""Tests for section-level visual keyword helpers."""

from futuredecoded.media.visual_keywords import (
    build_section_search_keywords,
    build_section_visual_prompt,
    score_video_tag_relevance,
)


def test_build_section_visual_prompt_prefers_entity_mapping():
    prompt = build_section_visual_prompt(
        "Hook",
        "OpenAI announces a major model release",
        "OpenAI GPT-5 Launch",
        visual_style="motion_graphics",
    )
    assert "openai" in prompt.lower() or "chatgpt" in prompt.lower()


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
