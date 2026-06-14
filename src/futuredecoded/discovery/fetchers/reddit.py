"""Reddit subreddit fetcher."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from futuredecoded.config.channel_profile import REDDIT_SUBREDDITS

logger = logging.getLogger("futuredecoded.discovery.reddit")


@dataclass
class RawStory:
    title: str
    url: str
    source: str
    score: int = 0


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def fetch_reddit_stories(limit_per_sub: int = 5) -> list[RawStory]:
    stories: list[RawStory] = []
    headers = {"User-Agent": "FutureDecodedBot/4.0"}
    for subreddit in REDDIT_SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit_per_sub}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
            for child in resp.json().get("data", {}).get("children", []):
                post = child.get("data", {})
                stories.append(
                    RawStory(
                        title=post.get("title", ""),
                        url=post.get("url", ""),
                        source=f"reddit_{subreddit}",
                        score=post.get("score", 0),
                    )
                )
        except Exception as exc:
            logger.warning("Reddit fetch failed r/%s: %s", subreddit, exc)
    return stories
