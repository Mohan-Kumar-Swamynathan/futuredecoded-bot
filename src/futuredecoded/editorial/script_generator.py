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
  "script_short": "45-60 second Shorts script. Structure: HOOK (3 sec) → PROBLEM → WHAT HAPPENED → WHY IT MATTERS → CTA. Short sentences. Mobile-first. ~120 words.",
  "script_long": "5-10 minute long-form script. Structure: Hook → Background → The News → Analysis → Future Impact → CTA. ~800-1200 words. Professional, engaging, fact-based."
}}

Channel: FutureDecoded — Making Sense of Tomorrow
Audience: developers, tech enthusiasts, startup founders
Style: news-first, curiosity gap, high retention
"""
    result = llm.call_json(prompt)
    scripts = GeneratedScripts(
        script_short=result.get("script_short", ""),
        script_long=result.get("script_long", ""),
        outline=result.get("outline", {}),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "script_short.txt").write_text(scripts.script_short, encoding="utf-8")
    (output_dir / "script_long.txt").write_text(scripts.script_long, encoding="utf-8")
    (output_dir / "outline.json").write_text(
        __import__("json").dumps(scripts.outline, indent=2), encoding="utf-8"
    )
    logger.info("Scripts generated for: %s", title[:60])
    return scripts
