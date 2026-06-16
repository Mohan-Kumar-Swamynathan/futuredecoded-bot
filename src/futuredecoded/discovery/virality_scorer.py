"""Virality and topic scoring engine — 4-axis model."""

from __future__ import annotations

import hashlib
import logging
import re
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
    "meta_ai": 85.0,
    "techcrunch": 88.0,
    "the_verge": 86.0,
    "ars_technica": 84.0,
    "wired": 83.0,
    "amazon_news": 82.0,
    "tesla_news": 80.0,
    "hacker_news": 82.0,
    "google_news": 88.0,
    "github_trending": 68.0,
}

NEWS_SOURCE_BOOST = 5.0
GITHUB_TRENDING_PENALTY = 12.0


@dataclass
class ScoredStory:
    title: str
    url: str
    source: str
    trend_score: float
    virality_score: float
    curiosity_score: float
    search_potential_score: float
    monetization_score: float
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


def _compute_curiosity_score(title: str) -> float:
    title_lower = title.lower()
    score = 40.0
    curiosity_words = ("why", "how", "what", "just", "new", "breakthrough", "first", "secret", "change")
    for word in curiosity_words:
        if word in title_lower:
            score += 8.0
    if "?" in title:
        score += 10.0
    return min(100.0, score)


def _compute_search_potential_score(title: str, source: str) -> float:
    title_lower = title.lower()
    score = _source_authority(source) * 0.5
    brand_keywords = (
        "openai", "google", "gemini", "gpt", "claude", "anthropic", "tesla", "nvidia",
        "amazon", "meta", "microsoft", "robotics", "startup", "ai",
    )
    for keyword in brand_keywords:
        if keyword in title_lower:
            score += 6.0
    return min(100.0, score)


def _compute_monetization_score(title: str, source: str) -> float:
    title_lower = title.lower()
    score = 70.0

    if source in {"google_news", "openai", "anthropic", "google_ai", "techcrunch", "the_verge"}:
        score += 12.0
    if source == "github_trending" or title_lower.startswith("trending:"):
        score -= 18.0

    risky_words = ("leak", "rumor", "unconfirmed", "scandal", "lawsuit", "death")
    for word in risky_words:
        if word in title_lower:
            score -= 15.0

    educational_words = ("launch", "announced", "update", "release", "partnership", "regulation")
    for word in educational_words:
        if word in title_lower:
            score += 4.0

    return max(20.0, min(100.0, score))


def _apply_source_adjustments(title: str, source: str, overall_score: float) -> float:
    adjusted = overall_score
    if source in {"google_news", "openai", "anthropic", "google_ai", "techcrunch", "the_verge", "wired"}:
        adjusted += NEWS_SOURCE_BOOST
    if source == "github_trending" or re.match(r"^trending:\s*", title, flags=re.IGNORECASE):
        adjusted -= GITHUB_TRENDING_PENALTY
    return max(0.0, min(99.0, adjusted))


def score_story(
    title: str,
    url: str,
    source: str,
    raw_score: int = 0,
    news_volume: float | None = None,
    social_mentions: float | None = None,
    published_at: float | None = None,
) -> ScoredStory:
    import time as _time
    engagement_signal = float(raw_score) if raw_score > 0 else 40.0
    # Recency boost: stories < 6h old get +8, < 24h +4, older get -5
    recency_boost = 0.0
    if published_at is not None:
        age_hours = (_time.time() - published_at) / 3600
        if age_hours < 6:
            recency_boost = 8.0
        elif age_hours < 24:
            recency_boost = 4.0
        elif age_hours > 72:
            recency_boost = -5.0
    search_growth = _normalize_score(engagement_signal, 250.0)
    news_vol = news_volume if news_volume is not None else _normalize_score(engagement_signal, 200.0)
    social = social_mentions if social_mentions is not None else _normalize_score(engagement_signal, 150.0)
    authority = _source_authority(source)
    engagement = _normalize_score(engagement_signal, 200.0)

    virality_score = min(99.0, 0.45 * social + 0.35 * search_growth + 0.20 * engagement)
    curiosity_score = _compute_curiosity_score(title)
    search_potential_score = _compute_search_potential_score(title, source)
    monetization_score = _compute_monetization_score(title, source)

    trend_score = (
        0.30 * virality_score
        + 0.25 * curiosity_score
        + 0.25 * search_potential_score
        + 0.20 * monetization_score
        + recency_boost
    )

    title_lower = title.lower()
    keyword_boost = 0.0
    for keyword in ("openai", "gpt", "gemini", "claude", "anthropic", "ai agent", "llm", "tesla", "nvidia"):
        if keyword in title_lower:
            keyword_boost += 3.0
    trend_score = _apply_source_adjustments(title, source, trend_score + keyword_boost)

    viral_probability = min(99.0, trend_score * 0.95)
    competition = max(10.0, 100.0 - trend_score * 0.5)
    content_hash = hashlib.sha256(f"{title}:{url}".encode()).hexdigest()

    if trend_score >= 85 and monetization_score >= 60:
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
        virality_score=round(virality_score, 2),
        curiosity_score=round(curiosity_score, 2),
        search_potential_score=round(search_potential_score, 2),
        monetization_score=round(monetization_score, 2),
        viral_probability=round(viral_probability, 2),
        competition=round(competition, 2),
        search_growth=f"{int(search_growth)}%",
        recommended_format=recommended_format,
        priority=priority,
        content_hash=content_hash,
    )


def _rank_stories(stories: list[ScoredStory]) -> list[ScoredStory]:
    return sorted(
        stories,
        key=lambda story: (story.trend_score, story.monetization_score),
        reverse=True,
    )


def select_ranked_stories(stories: list[ScoredStory], limit: int = 10) -> list[ScoredStory]:
    if not stories:
        return []

    settings = get_settings()
    threshold = settings.trend_score_threshold
    fallback_threshold = settings.trend_score_fallback_threshold
    ranked = _rank_stories(stories)

    top_scores = ", ".join(
        f"{story.trend_score:.1f}(m={story.monetization_score:.0f})" for story in ranked[:5]
    )
    logger.info("Top 5 trend scores: %s", top_scores)

    eligible = [story for story in ranked if story.trend_score >= threshold]
    if eligible:
        return eligible[:limit]

    fallback = [story for story in ranked if story.trend_score >= fallback_threshold]
    if fallback:
        logger.warning(
            "No story above threshold %d — returning fallback-ranked stories (best=%.1f)",
            threshold,
            fallback[0].trend_score,
        )
        return fallback[:limit]

    logger.info(
        "No stories above threshold %d or fallback %d (best=%.1f)",
        threshold,
        fallback_threshold,
        ranked[0].trend_score if ranked else 0.0,
    )
    return []


def select_best_story(stories: list[ScoredStory]) -> ScoredStory | None:
    ranked = select_ranked_stories(stories, limit=1)
    if not ranked:
        return None
    best = ranked[0]
    logger.info("Selected story (score=%.1f): %s", best.trend_score, best.title[:60])
    return best
