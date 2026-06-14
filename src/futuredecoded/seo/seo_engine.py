"""SEO enrichment engine — titles, descriptions, tags, social copy."""

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
    "title_score": 0-100,
    "description": "300+ words with summary, bullet points, timestamps/chapters, sources, CTA",
    "tags": ["15-20 tags"],
    "hashtags": ["#AI", "#OpenAI"],
    "chapters": [{{"time": "0:00", "label": "Hook"}}]
  }},
  "shorts": {{
    "title": "title with #Shorts",
    "description": "150 words hook + bullets + sources + CTA",
    "tags": ["15 tags"],
    "hashtags": ["#Shorts", "#AI"]
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
"""
    result = llm.call_json(prompt)
    seo = SeoMetadata(
        long_form=result.get("long_form", {}),
        shorts=result.get("shorts", {}),
        social=result.get("social", {}),
        keywords=result.get("keywords", {}),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "seo.json").write_text(
        json.dumps({
            "long_form": seo.long_form,
            "shorts": seo.shorts,
            "social": seo.social,
            "keywords": seo.keywords,
        }, indent=2),
        encoding="utf-8",
    )
    logger.info("SEO metadata saved for: %s", story_title[:50])
    return seo
