"""Title engine — 10 variants scored for CTR."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from futuredecoded.config.channel_profile import TITLE_VARIANT_COUNT
from futuredecoded.llm.provider_client import get_llm_client

logger = logging.getLogger("futuredecoded.editorial.titles")


@dataclass
class ScoredTitle:
    title: str
    ctr_score: float
    curiosity_score: float
    search_score: float
    total_score: float


def generate_and_score_titles(story_title: str, format_type: str = "long") -> ScoredTitle:
    llm = get_llm_client()
    prompt = f"""Generate {TITLE_VARIANT_COUNT} viral YouTube title variants for FutureDecoded.

Story: {story_title}
Format: {format_type}

Return JSON:
{{
  "titles": [
    {{"title": "...", "ctr_score": 0-100, "curiosity_score": 0-100, "search_score": 0-100}}
  ]
}}

Rules:
- Max 60 characters
- High CTR, curiosity gap, search value
- Examples: "OpenAI Just Changed Everything", "This AI Tool Is Scaring Developers"
- For shorts add #Shorts suffix to best title
"""
    result = llm.call_json(prompt)
    titles = result.get("titles", [])
    if not titles:
        fallback = ScoredTitle(story_title[:60], 50, 50, 50, 50)
        return fallback

    best = max(titles, key=lambda title: (
        title.get("ctr_score", 0) + title.get("curiosity_score", 0) + title.get("search_score", 0)
    ))
    total = (
        best.get("ctr_score", 0) * 0.4
        + best.get("curiosity_score", 0) * 0.35
        + best.get("search_score", 0) * 0.25
    )
    title_text = best.get("title", story_title)
    if format_type == "short" and "#Shorts" not in title_text:
        title_text = f"{title_text[:52]} #Shorts"

    scored = ScoredTitle(
        title=title_text[:100],
        ctr_score=float(best.get("ctr_score", 0)),
        curiosity_score=float(best.get("curiosity_score", 0)),
        search_score=float(best.get("search_score", 0)),
        total_score=round(total, 2),
    )
    logger.info("Best title (score=%.1f): %s", scored.total_score, scored.title[:50])
    return scored
