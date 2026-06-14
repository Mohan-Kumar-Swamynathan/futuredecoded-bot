"""Hacker News trending fetcher."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from futuredecoded.config.channel_profile import HN_API, TOPIC_KEYWORDS

logger = logging.getLogger("futuredecoded.discovery.hn")


@dataclass
class RawStory:
    title: str
    url: str
    source: str
    score: int = 0


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_hacker_news_stories(limit: int = 30) -> list[RawStory]:
    stories: list[RawStory] = []
    top_ids = requests.get(f"{HN_API}/topstories.json", timeout=15).json()[:limit * 2]
    keywords_lower = [keyword.lower() for keyword in TOPIC_KEYWORDS]

    for story_id in top_ids:
        if len(stories) >= limit:
            break
        try:
            item = requests.get(f"{HN_API}/item/{story_id}.json", timeout=10).json()
            if not item or item.get("type") != "story":
                continue
            title = item.get("title", "")
            if not any(keyword in title.lower() for keyword in keywords_lower):
                continue
            stories.append(
                RawStory(
                    title=title,
                    url=item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    source="hacker_news",
                    score=item.get("score", 0),
                )
            )
        except Exception as exc:
            logger.debug("HN item fetch failed: %s", exc)
    return stories
