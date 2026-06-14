"""Tests for virality scorer."""

from futuredecoded.discovery.virality_scorer import score_story, select_best_story


def test_score_story_above_threshold_for_hot_hn_story():
    story = score_story(
        title="OpenAI releases new AI agent builder",
        url="https://openai.com/blog",
        source="hacker_news",
        raw_score=350,
        news_volume=85.0,
        social_mentions=90.0,
    )
    assert story.trend_score >= 70


def test_select_best_story_uses_fallback_when_below_primary_threshold():
    low = score_story("Minor tool update", "https://a.com", "github_trending", raw_score=10)
    medium = score_story(
        "Google AI announces Gemini update",
        "https://blog.google",
        "google_news",
        raw_score=60,
        news_volume=85.0,
    )
    selected = select_best_story([low, medium])
    assert selected is not None
    assert selected.title == medium.title


def test_select_best_story_prefers_above_threshold():
    below = score_story("Low story", "https://a.com", "test", raw_score=5)
    above = score_story(
        "OpenAI GPT-5 launch breaks records",
        "https://openai.com",
        "openai",
        raw_score=500,
        news_volume=95.0,
        social_mentions=95.0,
    )
    selected = select_best_story([below, above])
    assert selected is not None
    assert selected.title == above.title
