"""Google News RSS fetcher."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

import feedparser
import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from futuredecoded.config.channel_profile import TOPIC_KEYWORDS

logger = logging.getLogger("futuredecoded.discovery.google_news")

_STOP_WORDS = frozenset({
    "a", "an", "and", "at", "for", "in", "is", "of", "on", "s", "the", "to", "u", "with",
})


@dataclass
class RawStory:
    title: str
    url: str
    source: str
    score: int = 0


@dataclass(frozen=True)
class NewsSourceReference:
    name: str
    url: str
    headline: str
    verified: bool = True


def _build_google_news_rss_url(query: str) -> str:
    encoded_query = quote(query)
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"


def _fetch_rss_feed(feed_url: str):
    response = requests.get(
        feed_url,
        headers={
            "User-Agent": "FutureDecodedBot/1.0 (+https://github.com/Mohan-Kumar-Swamynathan/futuredecoded-bot)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
        timeout=20,
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def _extract_publisher_name(entry: dict) -> str:
    source = entry.get("source")
    if isinstance(source, dict) and source.get("title"):
        return str(source["title"]).strip()
    title = str(entry.get("title", ""))
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Google News"


def _extract_headline(entry: dict) -> str:
    title = str(entry.get("title", ""))
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()


def _title_overlap_score(story_title: str, article_headline: str) -> float:
    story_tokens = {
        token for token in re.findall(r"[a-z0-9]+", story_title.lower()) if token not in _STOP_WORDS
    }
    article_tokens = {
        token for token in re.findall(r"[a-z0-9]+", article_headline.lower()) if token not in _STOP_WORDS
    }
    if not story_tokens:
        return 0.0
    return len(story_tokens & article_tokens) / len(story_tokens)


def _parse_news_references(feed_url: str, story_title: str, limit: int) -> list[NewsSourceReference]:
    references: list[NewsSourceReference] = []
    feed = _fetch_rss_feed(feed_url)
    ranked_entries: list[tuple[float, dict]] = []

    for entry in feed.entries:
        headline = _extract_headline(entry)
        overlap = _title_overlap_score(story_title, headline)
        ranked_entries.append((overlap, entry))

    ranked_entries.sort(key=lambda item: item[0], reverse=True)

    for overlap, entry in ranked_entries:
        if overlap < 0.15 and references:
            continue
        article_url = str(entry.get("link", "")).strip()
        if not article_url:
            continue
        references.append(
            NewsSourceReference(
                name=_extract_publisher_name(entry),
                url=article_url,
                headline=_extract_headline(entry),
                verified=True,
            )
        )
        if len(references) >= limit:
            break

    return references


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def search_google_news_for_story(story_title: str, limit: int = 5) -> list[NewsSourceReference]:
    """Search Google News RSS for corroborating coverage of a specific story."""
    if not story_title.strip():
        return []

    feed_url = _build_google_news_rss_url(story_title[:120])
    try:
        references = _parse_news_references(feed_url, story_title, limit)
        logger.info(
            "Google News search returned %d references for: %s",
            len(references),
            story_title[:60],
        )
        return references
    except Exception as exc:
        logger.warning("Google News search failed for '%s': %s", story_title[:60], exc)
        return []


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def fetch_google_news_stories(limit: int = 15) -> list[RawStory]:
    stories: list[RawStory] = []
    feed_url = _build_google_news_rss_url(" OR ".join(TOPIC_KEYWORDS[:6]))
    try:
        feed = _fetch_rss_feed(feed_url)
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
