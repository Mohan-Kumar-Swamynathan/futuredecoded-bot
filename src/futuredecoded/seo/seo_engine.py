"""SEO enrichment engine — titles, descriptions, tags, engagement copy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.config.channel_profile import CHANNEL_NAME, CHANNEL_TAGLINE
from futuredecoded.llm.provider_client import get_llm_client

logger = logging.getLogger("futuredecoded.seo.engine")


@dataclass
class SeoMetadata:
    long_form: dict
    shorts: dict
    social: dict
    keywords: dict


def enrich_seo(
    story_title: str,
    script_long: str,
    script_short: str,
    sources: list[str],
    output_dir: Path,
) -> SeoMetadata:
    llm = get_llm_client()
    sources_text = "\n".join(f"- {source}" for source in sources[:5])
    prompt = f"""Generate SEO-enriched YouTube metadata for FutureDecoded.

Channel: {CHANNEL_NAME} — {CHANNEL_TAGLINE}
Story: {story_title}

Sources:
{sources_text}

Return JSON:
{{
  "long_form": {{
    "title": "best title under 60 chars",
    "alternative_titles": ["alt 1", "alt 2", "alt 3"],
    "title_score": 0-100,
    "intro": "2-3 sentence summary paragraph. Plain text only.",
    "key_points": ["bullet 1", "bullet 2", "bullet 3", "bullet 4"],
    "tags": ["15-20 tags"],
    "hashtags": ["#AI", "#TechNews", "#FutureDecoded"],
    "pinned_comment": "engaging pinned comment inviting discussion",
    "community_post": "short community tab post for subscribers"
  }},
  "shorts": {{
    "title": "title with #Shorts",
    "alternative_titles": ["alt 1", "alt 2", "alt 3"],
    "hook": "1-2 sentence hook for Shorts description",
    "key_points": ["point 1", "point 2", "point 3"],
    "tags": ["15 tags"],
    "hashtags": ["#Shorts", "#AI", "#TechNews"],
    "pinned_comment": "short pinned comment for Shorts"
  }},
  "social": {{
    "x": "280 char post with link placeholder",
    "linkedin": "professional post",
    "telegram": "compact post with emoji"
  }},
  "keywords": {{
    "primary": ["OpenAI", "AI news"],
    "secondary": ["long tail keywords"]
  }}
}}

Rules:
- No timestamps/chapters — added automatically later
- No escaped newlines
- No markdown
- Titles must be accurate, not misleading clickbait
"""
    result = llm.call_json(prompt)
    seo = SeoMetadata(
        long_form=result.get("long_form", {}),
        shorts=result.get("shorts", {}),
        social=result.get("social", {}),
        keywords=result.get("keywords", {}),
    )

    seo_dir = output_dir / "seo"
    seo_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "long_form": seo.long_form,
        "shorts": seo.shorts,
        "social": seo.social,
        "keywords": seo.keywords,
    }
    (seo_dir / "seo.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output_dir / "seo.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("SEO metadata saved for: %s", story_title[:50])
    return seo
