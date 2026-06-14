"""30-day content calendar generator."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from futuredecoded.discovery.fetchers.google_news import fetch_google_news_stories
from futuredecoded.discovery.fetchers.hacker_news import fetch_hacker_news_stories
from futuredecoded.discovery.fetchers.rss_feeds import fetch_rss_stories
from futuredecoded.discovery.virality_scorer import score_story
from futuredecoded.editorial.content_strategist import decide_format, generate_content_calendar

logger = logging.getLogger("futuredecoded.pipeline.calendar")


def build_content_calendar(output_path: Path) -> None:
    raw_stories = []
    raw_stories.extend(fetch_hacker_news_stories(limit=20))
    raw_stories.extend(fetch_rss_stories(limit_per_feed=5))
    raw_stories.extend(fetch_google_news_stories(limit=20))

    scored = []
    seen: set[str] = set()
    for raw in raw_stories:
        story = score_story(raw.title, raw.url, raw.source, raw.score)
        if story.content_hash in seen:
            continue
        seen.add(story.content_hash)
        if story.trend_score > 60:
            scored.append(story)

    scored.sort(key=lambda story: story.trend_score, reverse=True)
    generate_content_calendar(scored[:30], output_path)
    logger.info("Calendar written: %s", output_path)
