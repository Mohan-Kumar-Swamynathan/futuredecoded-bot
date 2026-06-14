"""Dual script generator — Shorts + Long-form."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.llm.provider_client import get_llm_client

logger = logging.getLogger("futuredecoded.editorial.scripts")


@dataclass
class GeneratedScripts:
    script_short: str
    script_long: str
    outline: dict
    script_sections: list[dict[str, str]]
    script_short_sections: list[dict[str, str]]


def generate_scripts(title: str, url: str, output_dir: Path) -> GeneratedScripts:
    llm = get_llm_client()
    prompt = f"""Write YouTube scripts for FutureDecoded — fast-paced AI/tech news channel.

Story: {title}
Source: {url}

Return JSON:
{{
  "outline": {{
    "hook": "...",
    "key_facts": ["...", "..."],
    "impact": "...",
    "sources": ["{url}"]
  }},
  "script_sections": [
    {{"label": "Hook", "text": "opening hook narration"}},
    {{"label": "Background", "text": "context narration"}},
    {{"label": "The News", "text": "main story narration"}},
    {{"label": "Analysis", "text": "analysis narration"}},
    {{"label": "Future Impact", "text": "future impact narration"}},
    {{"label": "Wrap Up", "text": "closing CTA narration"}}
  ],
  "script_short_sections": [
    {{"label": "Hook", "text": "short hook"}},
    {{"label": "What Happened", "text": "short explanation"}},
    {{"label": "Why It Matters", "text": "short impact"}},
    {{"label": "Takeaway", "text": "short CTA"}}
  ],
  "script_short": "45-60 second Shorts script as one continuous narration. ~120 words.",
  "script_long": "Full long-form narration combining all script_sections in order. ~800-1200 words."
}}

Channel: FutureDecoded — Making Sense of Tomorrow
Audience: developers, tech enthusiasts, startup founders
Style: news-first, curiosity gap, high retention
"""
    result = llm.call_json(prompt)
    script_sections = result.get("script_sections", [])
    script_short_sections = result.get("script_short_sections", [])
    script_long = result.get("script_long", "") or _combine_sections(script_sections)
    script_short = result.get("script_short", "") or _combine_sections(script_short_sections)

    scripts = GeneratedScripts(
        script_short=script_short,
        script_long=script_long,
        outline=result.get("outline", {}),
        script_sections=script_sections,
        script_short_sections=script_short_sections,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "script_short.txt").write_text(scripts.script_short, encoding="utf-8")
    (output_dir / "script_long.txt").write_text(scripts.script_long, encoding="utf-8")
    (output_dir / "script_sections.json").write_text(
        __import__("json").dumps({
            "long": scripts.script_sections,
            "short": scripts.script_short_sections,
        }, indent=2),
        encoding="utf-8",
    )
    (output_dir / "outline.json").write_text(
        __import__("json").dumps(scripts.outline, indent=2), encoding="utf-8"
    )
    logger.info("Scripts generated for: %s", title[:60])
    return scripts


def _combine_sections(sections: list[dict[str, str]]) -> str:
    narration_parts = []
    for section in sections:
        section_text = str(section.get("text", "")).strip()
        if section_text:
            narration_parts.append(section_text)
    return "\n\n".join(narration_parts)
