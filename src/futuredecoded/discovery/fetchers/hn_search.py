"""Hacker News search for dev-story corroboration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from futuredecoded.discovery.news_query_builder import normalize_story_title_for_search

logger = logging.getLogger("futuredecoded.discovery.hn_search")

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


@dataclass(frozen=True)
class HnDiscussionReference:
    name: str
    url: str
    headline: str
    verified: bool = True


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def search_hn_discussions(story_title: str, limit: int = 3) -> list[HnDiscussionReference]:
    query = normalize_story_title_for_search(story_title)
    if not query:
        return []

    try:
        response = requests.get(
            HN_ALGOLIA_URL,
            params={"query": query, "tags": "story", "hitsPerPage": limit},
            timeout=15,
        )
        response.raise_for_status()
        references: list[HnDiscussionReference] = []
        for hit in response.json().get("hits", [])[:limit]:
            object_id = hit.get("objectID", "")
            headline = str(hit.get("title", query))
            if not object_id:
                continue
            references.append(
                HnDiscussionReference(
                    name="Hacker News",
                    url=f"https://news.ycombinator.com/item?id={object_id}",
                    headline=headline,
                )
            )
        logger.info("HN search returned %d discussions for: %s", len(references), query[:50])
        return references
    except Exception as exc:
        logger.warning("HN search failed for '%s': %s", query[:50], exc)
        return []
