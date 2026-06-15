"""Tests for content format decisions."""

from futuredecoded.discovery.virality_scorer import score_story
from futuredecoded.editorial.content_strategist import decide_format
from futuredecoded.config.channel_profile import ContentFormat


def test_decide_format_returns_both_for_anthropic_story():
    story = score_story(
        title="Anthropic's Safety Superpower",
        url="https://example.com",
        source="hacker_news",
        raw_score=120,
    )
    assert decide_format(story) == ContentFormat.BOTH


def test_decide_format_returns_both_for_medium_score_fallback_story():
    story = score_story(
        title="Minor developer tooling update",
        url="https://example.com",
        source="github_trending",
        raw_score=20,
    )
    assert decide_format(story) == ContentFormat.BOTH
