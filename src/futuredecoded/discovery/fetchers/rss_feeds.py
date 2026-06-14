"""RSS feed fetcher for AI blog sources."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser
from tenacity import retry, stop_after_attempt, wait_fixed

from futuredecoded.config.channel_profile import RSS_FEEDS

logger = logging.getLogger("futuredecoded.discovery.rss")


@dataclass
class RawStory:
    title: str
    url: str
    source: str
    score: int = 0


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def fetch_rss_stories(limit_per_feed: int = 5) -> list[RawStory]:
    stories: list[RawStory] = []
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:limit_per_feed]:
                stories.append(
                    RawStory(
                        title=entry.get("title", "Untitled"),
                        url=entry.get("link", ""),
                        source=source_name,
                        score=50,
                    )
                )
        except Exception as exc:
            logger.warning("RSS fetch failed for %s: %s", source_name, exc)
    return stories
