"""Tests for virality scorer."""

from futuredecoded.discovery.virality_scorer import score_story, select_best_story


def test_score_story_above_threshold():
    story = score_story(
        title="OpenAI releases new AI agent builder",
        url="https://openai.com/blog",
        source="openai",
        raw_score=400,
    )
    assert story.trend_score > 50
    assert story.content_hash


def test_select_best_story_filters_low_scores():
    low = score_story("Low story", "https://a.com", "test", raw_score=1)
    high = score_story(
        "OpenAI GPT-5 launch",
        "https://openai.com",
        "openai",
        raw_score=500,
        news_volume=100.0,
        social_mentions=100.0,
    )
    selected = select_best_story([low, high])
    assert selected is not None
    assert selected.title == high.title
