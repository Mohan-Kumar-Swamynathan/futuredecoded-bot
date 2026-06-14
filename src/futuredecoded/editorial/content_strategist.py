"""Content strategist — decides Short / Long / Both."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from futuredecoded.config.channel_profile import ContentFormat, StoryCategory
from futuredecoded.discovery.virality_scorer import ScoredStory

logger = logging.getLogger("futuredecoded.editorial.strategist")


def decide_format(story: ScoredStory) -> ContentFormat:
    title_lower = story.title.lower()
    if any(word in title_lower for word in ("launch", "released", "gpt", "gemini", "claude")):
        return ContentFormat.BOTH
    if any(word in title_lower for word in ("breaking", "just", "announced")):
        return ContentFormat.SHORT
    if any(word in title_lower for word in ("how", "explained", "guide", "works")):
        return ContentFormat.LONG
    if story.recommended_format == "both":
        return ContentFormat.BOTH
    if story.recommended_format == "shorts":
        return ContentFormat.SHORT
    return ContentFormat.BOTH


def generate_content_calendar(stories: list[ScoredStory], output_path: Path) -> None:
    calendar = []
    for index, story in enumerate(stories[:30]):
        calendar.append({
            "day": index + 1,
            "title": story.title,
            "format": decide_format(story).value,
            "trend_score": story.trend_score,
            "priority": story.priority,
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(calendar, indent=2), encoding="utf-8")
    logger.info("Content calendar saved: %s (%d days)", output_path, len(calendar))
