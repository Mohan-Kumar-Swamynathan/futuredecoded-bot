"""Dual script generator — journalist-grade long + Shorts scripts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.llm.provider_client import get_llm_client
from futuredecoded.research.research_engine import ResearchBundle

logger = logging.getLogger("futuredecoded.editorial.scripts")


@dataclass
class GeneratedScripts:
    script_short: str
    script_long: str
    outline: dict
    script_sections: list[dict[str, str]]
    script_short_sections: list[dict[str, str]]


def generate_scripts(
    title: str,
    url: str,
    output_dir: Path,
    research: ResearchBundle | None = None,
) -> GeneratedScripts:
    llm = get_llm_client()
    research_context = ""
    if research:
        research_context = "\n".join(f"- {point}" for point in research.summary_points[:6])

    prompt = f"""Write original YouTube scripts for FutureDecoded — a technology news channel.

Story: {title}
Source: {url}

Research context:
{research_context or "Use the primary source and add original analysis."}

Return JSON:
{{
  "outline": {{
    "hook": "...",
    "key_facts": ["...", "..."],
    "impact": "...",
    "sources": ["{url}"]
  }},
  "script_sections": [
    {{"label": "Hook", "text": "0-15 second curiosity hook"}},
    {{"label": "Problem", "text": "problem or context"}},
    {{"label": "What Happened", "text": "what happened"}},
    {{"label": "Why It Matters", "text": "why it matters"}},
    {{"label": "Industry Impact", "text": "industry impact"}},
    {{"label": "Future Outlook", "text": "future outlook"}},
    {{"label": "Call To Action", "text": "subscribe CTA"}}
  ],
  "script_short_sections": [
    {{"label": "Hook", "text": "3-second hook"}},
    {{"label": "Key Fact", "text": "single key fact"}},
    {{"label": "Why It Matters", "text": "one sentence impact"}},
    {{"label": "Takeaway", "text": "CTA"}}
  ],
  "script_short": "30-60 second Shorts narration. ~80-120 words. Conversational.",
  "script_long": "4-6 minute narration combining all script_sections. 600-900 words."
}}

Channel: FutureDecoded — Making Sense of Tomorrow
Audience: developers, tech enthusiasts, startup founders, AI enthusiasts

Rules:
- Original commentary and analysis — do NOT rewrite a press release
- Explain why the news matters
- Conversational, not robotic
- No repeated phrases
- No generic filler like "in today's video" or "without further ado"
- Short sentences for retention
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

    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "script_short.txt").write_text(scripts.script_short, encoding="utf-8")
    (scripts_dir / "script_long.txt").write_text(scripts.script_long, encoding="utf-8")
    (scripts_dir / "script_sections.json").write_text(
        json.dumps({"long": scripts.script_sections, "short": scripts.script_short_sections}, indent=2),
        encoding="utf-8",
    )
    (scripts_dir / "outline.json").write_text(json.dumps(scripts.outline, indent=2), encoding="utf-8")
    (output_dir / "script_short.txt").write_text(scripts.script_short, encoding="utf-8")
    (output_dir / "script_long.txt").write_text(scripts.script_long, encoding="utf-8")
    logger.info("Scripts generated for: %s", title[:60])
    return scripts


def _combine_sections(sections: list[dict[str, str]]) -> str:
    narration_parts = []
    for section in sections:
        section_text = str(section.get("text", "")).strip()
        if section_text:
            narration_parts.append(section_text)
    return "\n\n".join(narration_parts)
