"""Virality scoring engine."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from futuredecoded.config.settings import get_settings

logger = logging.getLogger("futuredecoded.discovery.scorer")


@dataclass
class ScoredStory:
    title: str
    url: str
    source: str
    trend_score: float
    viral_probability: float
    competition: float
    search_growth: str
    recommended_format: str
    priority: str
    content_hash: str


def _normalize_score(value: float, max_value: float = 100.0) -> float:
    return min(100.0, max(0.0, (value / max_value) * 100.0))


def score_story(
    title: str,
    url: str,
    source: str,
    raw_score: int = 0,
    news_volume: float = 50.0,
    social_mentions: float = 50.0,
) -> ScoredStory:
    search_growth = _normalize_score(raw_score, 500.0)
    news_vol = _normalize_score(news_volume, 100.0)
    social = _normalize_score(social_mentions, 100.0)
    authority = 70.0 if source in ("openai", "anthropic", "google_ai", "deepmind") else 55.0
    engagement = _normalize_score(raw_score, 300.0)

    trend_score = (
        0.30 * search_growth
        + 0.25 * news_vol
        + 0.20 * social
        + 0.15 * authority
        + 0.10 * engagement
    )

    viral_probability = min(99.0, trend_score * 0.95)
    competition = max(10.0, 100.0 - trend_score * 0.5)
    content_hash = hashlib.sha256(f"{title}:{url}".encode()).hexdigest()

    if trend_score >= 90:
        recommended_format = "both"
        priority = "high"
    elif trend_score >= 80:
        recommended_format = "shorts"
        priority = "high"
    else:
        recommended_format = "skip"
        priority = "low"

    return ScoredStory(
        title=title,
        url=url,
        source=source,
        trend_score=round(trend_score, 2),
        viral_probability=round(viral_probability, 2),
        competition=round(competition, 2),
        search_growth=f"{int(search_growth)}%",
        recommended_format=recommended_format,
        priority=priority,
        content_hash=content_hash,
    )


def select_best_story(stories: list[ScoredStory]) -> ScoredStory | None:
    threshold = get_settings().trend_score_threshold
    eligible = [story for story in stories if story.trend_score > threshold]
    if not eligible:
        logger.info("No stories above threshold %d", threshold)
        return None
    return max(eligible, key=lambda story: story.trend_score)
