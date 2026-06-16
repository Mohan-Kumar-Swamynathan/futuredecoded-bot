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

    # Pass actual script content so titles/descriptions match what was said
    script_excerpt_long = script_long[:2000] if script_long else ""
    script_excerpt_short = script_short[:500] if script_short else ""

    prompt = f"""Generate SEO-optimised YouTube metadata for FutureDecoded.

Channel: {CHANNEL_NAME} — {CHANNEL_TAGLINE}
Story: {story_title}

Long-form script (first 2000 chars):
{script_excerpt_long}

Shorts script:
{script_excerpt_short}

Sources:
{sources_text}

Return JSON:
{{
  "long_form": {{
    "title": "Under 60 chars. Lead with the most surprising element — a number, a name, or a counterintuitive fact. No 'FutureDecoded' in title. Examples: 'OpenAI Just Changed How Agents Work', 'Why Every Dev Should Know About This Model', 'Google DeepMind Beat GPT-4 at This'",
    "alternative_titles": ["alt 1 — curiosity angle", "alt 2 — search angle", "alt 3 — controversy angle"],
    "title_score": 0,
    "intro": "2-3 sentence hook paragraph matching the video opening energy. Must make viewer want to keep watching. Plain text only.",
    "key_points": ["specific takeaway 1 with number or example", "specific takeaway 2", "specific takeaway 3", "specific takeaway 4"],
    "tags": ["15-20 tags — mix of brand names, topics, and long-tail search phrases"],
    "hashtags": ["#AI", "#TechNews", "#FutureDecoded", "#topic-specific"],
    "pinned_comment": "Ask a specific two-choice question from the video — forces replies. Example: 'Would you switch to this over GPT-4? Drop your pick below 👇'",
    "community_post": "Short teaser that creates FOMO — what did viewers just miss? 1-2 sentences."
  }},
  "shorts": {{
    "title": "Under 60 chars + #Shorts. The hook as a title — a surprising number or claim.",
    "alternative_titles": ["alt 1", "alt 2", "alt 3"],
    "hook": "One sentence that stops the scroll. Start with the most surprising fact from the short script.",
    "key_points": ["point 1", "point 2", "point 3"],
    "tags": ["15 tags — prioritise trending and brand terms"],
    "hashtags": ["#Shorts", "#AI", "#TechNews", "#topic-specific"],
    "pinned_comment": "One-line question with emoji. Under 100 chars."
  }},
  "social": {{
    "x": "Under 280 chars. Hook + key fact + [link]. Conversational, not press-release.",
    "linkedin": "Professional framing — implications for teams or founders. 2-3 sentences.",
    "telegram": "Emoji + punchy summary + link placeholder. Under 200 chars."
  }},
  "keywords": {{
    "primary": ["3-5 high-volume brand/topic terms from the script"],
    "secondary": ["5-8 long-tail search phrases people actually type"]
  }}
}}

TITLE RULES (CTR is everything):
- Numbers outperform: '3x faster', '$1B deal', '10M users'
- Questions work: 'Is This the End of X?', 'Why Did Y Do This?'
- Counterintuitive beats obvious: 'The AI Nobody's Talking About' > 'New AI Model Released'
- Never start with 'How', 'Why', 'What' alone — add specificity
- No misleading clickbait — must match what the video actually covers

KEY_POINTS must be specific takeaways a viewer learned — not vague topic labels.
Bad: "Discussion of OpenAI's new model"
Good: "GPT-5 processes 10x longer context than GPT-4 at the same price"
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
