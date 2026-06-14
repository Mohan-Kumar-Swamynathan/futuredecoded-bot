"""Google News RSS fetcher."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

import feedparser
from tenacity import retry, stop_after_attempt, wait_fixed

from futuredecoded.config.channel_profile import TOPIC_KEYWORDS

logger = logging.getLogger("futuredecoded.discovery.google_news")


@dataclass
class RawStory:
    title: str
    url: str
    source: str
    score: int = 0


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def fetch_google_news_stories(limit: int = 15) -> list[RawStory]:
    stories: list[RawStory] = []
    query = quote(" OR ".join(TOPIC_KEYWORDS[:6]))
    feed_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            stories.append(
                RawStory(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    source="google_news",
                    score=60,
                )
            )
    except Exception as exc:
        logger.warning("Google News fetch failed: %s", exc)
    return stories
