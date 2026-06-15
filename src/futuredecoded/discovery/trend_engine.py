"""Trend discovery orchestrator — aggregates all fetchers."""

from __future__ import annotations

import logging

from futuredecoded.discovery.fetchers.github_trending import fetch_github_trending
from futuredecoded.discovery.fetchers.google_news import fetch_google_news_stories
from futuredecoded.discovery.fetchers.hacker_news import fetch_hacker_news_stories
from futuredecoded.discovery.fetchers.reddit import fetch_reddit_stories
from futuredecoded.discovery.fetchers.rss_feeds import fetch_rss_stories
from futuredecoded.discovery.virality_scorer import ScoredStory, score_story, select_best_story, select_ranked_stories

logger = logging.getLogger("futuredecoded.discovery.engine")


def _news_volume_signal(source: str, raw_score: int) -> float:
    if source == "google_news":
        return 85.0
    if source in ("openai", "anthropic", "google_ai", "deepmind"):
        return 90.0
    return min(100.0, 50.0 + raw_score / 5.0)


def _social_signal(source: str, raw_score: int) -> float:
    if source.startswith("reddit_"):
        return min(100.0, 40.0 + raw_score / 3.0)
    if source == "hacker_news":
        return min(100.0, 35.0 + raw_score / 4.0)
    return min(100.0, 45.0 + raw_score / 6.0)


def discover_ranked_stories(limit: int = 10) -> list[ScoredStory]:
    raw_stories = []
    raw_stories.extend(fetch_hacker_news_stories())
    raw_stories.extend(fetch_rss_stories())
    raw_stories.extend(fetch_reddit_stories())
    raw_stories.extend(fetch_google_news_stories())
    raw_stories.extend(fetch_github_trending())

    logger.info("Discovered %d raw stories", len(raw_stories))

    scored: list[ScoredStory] = []
    seen_hashes: set[str] = set()
    for raw in raw_stories:
        if not raw.title or not raw.url:
            continue
        story = score_story(
            title=raw.title,
            url=raw.url,
            source=raw.source,
            raw_score=raw.score,
            news_volume=_news_volume_signal(raw.source, raw.score),
            social_mentions=_social_signal(raw.source, raw.score),
        )
        if story.content_hash in seen_hashes:
            continue
        seen_hashes.add(story.content_hash)
        scored.append(story)

    return select_ranked_stories(scored, limit=limit)


def discover_and_score() -> ScoredStory | None:
    return select_best_story(_collect_scored_stories())


def _collect_scored_stories() -> list[ScoredStory]:
    raw_stories = []
    raw_stories.extend(fetch_hacker_news_stories())
    raw_stories.extend(fetch_rss_stories())
    raw_stories.extend(fetch_reddit_stories())
    raw_stories.extend(fetch_google_news_stories())
    raw_stories.extend(fetch_github_trending())

    logger.info("Discovered %d raw stories", len(raw_stories))

    scored: list[ScoredStory] = []
    seen_hashes: set[str] = set()
    for raw in raw_stories:
        if not raw.title or not raw.url:
            continue
        story = score_story(
            title=raw.title,
            url=raw.url,
            source=raw.source,
            raw_score=raw.score,
            news_volume=_news_volume_signal(raw.source, raw.score),
            social_mentions=_social_signal(raw.source, raw.score),
        )
        if story.content_hash in seen_hashes:
            continue
        seen_hashes.add(story.content_hash)
        scored.append(story)
    return scored
