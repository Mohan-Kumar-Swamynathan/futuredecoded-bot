"""GitHub trending repositories fetcher."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger("futuredecoded.discovery.github")


@dataclass
class RawStory:
    title: str
    url: str
    source: str
    score: int = 0


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def fetch_github_trending(limit: int = 10) -> list[RawStory]:
    stories: list[RawStory] = []
    since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"AI machine-learning created:>{since}"
    url = "https://api.github.com/search/repositories"
    try:
        resp = requests.get(
            url,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=15,
        )
        if resp.status_code != 200:
            return stories
        for repo in resp.json().get("items", []):
            stories.append(
                RawStory(
                    title=f"Trending: {repo.get('full_name', '')} — {repo.get('description', '')[:80]}",
                    url=repo.get("html_url", ""),
                    source="github_trending",
                    score=repo.get("stargazers_count", 0),
                )
            )
    except Exception as exc:
        logger.warning("GitHub trending fetch failed: %s", exc)
    return stories
