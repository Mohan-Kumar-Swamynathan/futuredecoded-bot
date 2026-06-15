"""Multi-source research engine — gathers context before scripting."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.discovery.fetchers.google_news import search_google_news_for_story
from futuredecoded.discovery.fetchers.hn_search import search_hn_discussions
from futuredecoded.discovery.news_query_builder import build_news_search_queries

logger = logging.getLogger("futuredecoded.research")


@dataclass
class ResearchSource:
    name: str
    url: str
    headline: str
    source_type: str


@dataclass
class ResearchBundle:
    story_title: str
    primary_url: str
    sources: list[ResearchSource]
    search_queries: list[str]
    summary_points: list[str]


def gather_research(
    title: str,
    url: str,
    source: str,
    fact_check_sources: list[dict],
    output_dir: Path,
) -> ResearchBundle:
    search_queries = build_news_search_queries(title)
    sources: list[ResearchSource] = []

    for fact_source in fact_check_sources:
        sources.append(
            ResearchSource(
                name=str(fact_source.get("name", "Source")),
                url=str(fact_source.get("url", "")),
                headline=str(fact_source.get("headline", title)),
                source_type="fact_check",
            )
        )

    for reference in search_google_news_for_story(title, limit=3):
        sources.append(
            ResearchSource(
                name=reference.name,
                url=reference.url,
                headline=reference.headline,
                source_type="google_news",
            )
        )

    if source in ("github_trending", "hacker_news"):
        for discussion in search_hn_discussions(title, limit=2):
            sources.append(
                ResearchSource(
                    name=discussion.name,
                    url=discussion.url,
                    headline=discussion.headline,
                    source_type="hacker_news",
                )
            )

    deduped = _dedupe_sources(sources)
    summary_points = [
        f"{item.name}: {item.headline[:120]}"
        for item in deduped[:5]
        if item.headline
    ]

    bundle = ResearchBundle(
        story_title=title,
        primary_url=url,
        sources=deduped,
        search_queries=search_queries,
        summary_points=summary_points or [title],
    )

    research_dir = output_dir / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "sources.json").write_text(
        json.dumps({
            "title": title,
            "primary_url": url,
            "source": source,
            "search_queries": search_queries,
            "sources": [
                {
                    "name": item.name,
                    "url": item.url,
                    "headline": item.headline,
                    "source_type": item.source_type,
                }
                for item in deduped
            ],
            "summary_points": summary_points,
        }, indent=2),
        encoding="utf-8",
    )
    logger.info("Research gathered: %d sources for %s", len(deduped), title[:50])
    return bundle


def _dedupe_sources(sources: list[ResearchSource]) -> list[ResearchSource]:
    seen_urls: set[str] = set()
    deduped: list[ResearchSource] = []
    for source in sources:
        if not source.url or source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        deduped.append(source)
    return deduped
