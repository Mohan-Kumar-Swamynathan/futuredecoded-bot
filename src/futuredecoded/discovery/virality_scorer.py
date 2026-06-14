"""Virality scoring engine."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from futuredecoded.config.settings import get_settings

logger = logging.getLogger("futuredecoded.discovery.scorer")

SOURCE_AUTHORITY: dict[str, float] = {
    "openai": 95.0,
    "anthropic": 95.0,
    "google_ai": 90.0,
    "deepmind": 90.0,
    "microsoft_ai": 85.0,
    "nvidia_ai": 85.0,
    "hacker_news": 82.0,
    "google_news": 78.0,
    "github_trending": 75.0,
}


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


def _source_authority(source: str) -> float:
    if source in SOURCE_AUTHORITY:
        return SOURCE_AUTHORITY[source]
    if source.startswith("reddit_"):
        return 72.0
    return 62.0


def score_story(
    title: str,
    url: str,
    source: str,
    raw_score: int = 0,
    news_volume: float | None = None,
    social_mentions: float | None = None,
) -> ScoredStory:
    engagement_signal = float(raw_score) if raw_score > 0 else 40.0
    search_growth = _normalize_score(engagement_signal, 250.0)
    news_vol = news_volume if news_volume is not None else _normalize_score(engagement_signal, 200.0)
    social = social_mentions if social_mentions is not None else _normalize_score(engagement_signal, 150.0)
    authority = _source_authority(source)
    engagement = _normalize_score(engagement_signal, 200.0)

    trend_score = (
        0.30 * search_growth
        + 0.25 * news_vol
        + 0.20 * social
        + 0.15 * authority
        + 0.10 * engagement
    )

    # Boost breaking AI keywords
    title_lower = title.lower()
    keyword_boost = 0.0
    for keyword in ("openai", "gpt", "gemini", "claude", "anthropic", "ai agent", "llm"):
        if keyword in title_lower:
            keyword_boost += 3.0
    trend_score = min(99.0, trend_score + keyword_boost)

    viral_probability = min(99.0, trend_score * 0.95)
    competition = max(10.0, 100.0 - trend_score * 0.5)
    content_hash = hashlib.sha256(f"{title}:{url}".encode()).hexdigest()

    if trend_score >= 85:
        recommended_format = "both"
        priority = "high"
    elif trend_score >= 70:
        recommended_format = "shorts"
        priority = "high"
    elif trend_score >= 55:
        recommended_format = "shorts"
        priority = "medium"
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
    if not stories:
        return None

    settings = get_settings()
    threshold = settings.trend_score_threshold
    fallback_threshold = settings.trend_score_fallback_threshold

    ranked = sorted(stories, key=lambda story: story.trend_score, reverse=True)
    top_scores = ", ".join(f"{story.trend_score:.1f}" for story in ranked[:5])
    logger.info("Top 5 trend scores: %s", top_scores)

    eligible = [story for story in stories if story.trend_score >= threshold]
    if eligible:
        best = max(eligible, key=lambda story: story.trend_score)
        logger.info("Selected story above threshold %d (score=%.1f)", threshold, best.trend_score)
        return best

    best_overall = ranked[0]
    if best_overall.trend_score >= fallback_threshold:
        logger.warning(
            "No story above threshold %d — using fallback best (score=%.1f): %s",
            threshold,
            best_overall.trend_score,
            best_overall.title[:60],
        )
        return best_overall

    logger.info(
        "No stories above threshold %d or fallback %d (best=%.1f)",
        threshold,
        fallback_threshold,
        best_overall.trend_score,
    )
    return None
