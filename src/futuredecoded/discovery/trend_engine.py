"""Trend discovery orchestrator — aggregates all fetchers."""

from __future__ import annotations

import logging

from futuredecoded.discovery.fetchers.github_trending import fetch_github_trending
from futuredecoded.discovery.fetchers.google_news import fetch_google_news_stories
from futuredecoded.discovery.fetchers.hacker_news import fetch_hacker_news_stories
from futuredecoded.discovery.fetchers.reddit import fetch_reddit_stories
from futuredecoded.discovery.fetchers.rss_feeds import fetch_rss_stories
from futuredecoded.discovery.virality_scorer import ScoredStory, score_story, select_best_story

logger = logging.getLogger("futuredecoded.discovery.engine")


def discover_and_score() -> ScoredStory | None:
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
        )
        if story.content_hash in seen_hashes:
            continue
        seen_hashes.add(story.content_hash)
        scored.append(story)

    return select_best_story(scored)
