"""Dual script generator — journalist-grade long + Shorts scripts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.editorial.compliance_guard import MIN_LONG_SCRIPT_WORDS
from futuredecoded.llm.provider_client import get_llm_client
from futuredecoded.research.research_engine import ResearchBundle

logger = logging.getLogger("futuredecoded.editorial.scripts")

MAX_SCRIPT_GENERATION_ATTEMPTS = 3


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
    research_context = _build_research_context(research)
    scripts: GeneratedScripts | None = None

    for attempt_index in range(1, MAX_SCRIPT_GENERATION_ATTEMPTS + 1):
        prompt = _build_generation_prompt(
            title=title,
            url=url,
            research_context=research_context,
            attempt_index=attempt_index,
        )
        result = llm.call_json(prompt)
        scripts = _build_scripts_from_result(result, url)
        word_count = _count_words(scripts.script_long)

        if word_count >= MIN_LONG_SCRIPT_WORDS:
            logger.info("Long script ready: %d words (attempt %d)", word_count, attempt_index)
            break

        logger.warning(
            "Long script too short (%d words, min %d) — attempt %d/%d",
            word_count,
            MIN_LONG_SCRIPT_WORDS,
            attempt_index,
            MAX_SCRIPT_GENERATION_ATTEMPTS,
        )
        if attempt_index < MAX_SCRIPT_GENERATION_ATTEMPTS:
            scripts = _expand_long_script(llm, title, url, research_context, scripts)
            expanded_word_count = _count_words(scripts.script_long)
            if expanded_word_count >= MIN_LONG_SCRIPT_WORDS:
                logger.info("Long script expanded: %d words", expanded_word_count)
                break

    if scripts is None:
        raise RuntimeError(f"Failed to generate scripts for: {title[:60]}")

    _persist_scripts(scripts, output_dir, title)
    return scripts


def _build_research_context(research: ResearchBundle | None) -> str:
    if not research:
        return "Use the primary source and add original analysis."
    return "\n".join(f"- {point}" for point in research.summary_points[:6])


def _build_generation_prompt(
    title: str,
    url: str,
    research_context: str,
    attempt_index: int,
) -> str:
    strictness = ""
    if attempt_index > 1:
        strictness = (
            f"\nCRITICAL (attempt {attempt_index}): Your previous response was too short. "
            f"script_long MUST be at least {MIN_LONG_SCRIPT_WORDS} words. "
            "Each script_sections entry needs 80-120 words of spoken narration."
        )

    return f"""Write original YouTube scripts for FutureDecoded — a technology news channel.

Story: {title}
Source: {url}

Research context:
{research_context}
{strictness}

Return JSON:
{{
  "outline": {{
    "hook": "...",
    "key_facts": ["...", "..."],
    "impact": "...",
    "sources": ["{url}"]
  }},
  "script_sections": [
    {{"label": "Hook", "text": "15-second spoken hook (~30 words)"}},
    {{"label": "Problem", "text": "context paragraph (~90 words)"}},
    {{"label": "What Happened", "text": "news summary (~100 words)"}},
    {{"label": "Why It Matters", "text": "analysis (~100 words)"}},
    {{"label": "Industry Impact", "text": "impact (~100 words)"}},
    {{"label": "Future Outlook", "text": "outlook (~100 words)"}},
    {{"label": "Call To Action", "text": "CTA (~40 words)"}}
  ],
  "script_short_sections": [
    {{"label": "Hook", "text": "3-second hook"}},
    {{"label": "Key Fact", "text": "single key fact"}},
    {{"label": "Why It Matters", "text": "one sentence impact"}},
    {{"label": "Takeaway", "text": "CTA"}}
  ],
  "script_short": "30-60 second Shorts narration. 80-120 words total.",
  "script_long": "Full 4-6 minute narration. MUST be 600-900 words. Combine all sections."
}}

Channel: FutureDecoded — Making Sense of Tomorrow
Audience: developers, tech enthusiasts, startup founders, AI enthusiasts

Rules:
- script_long word count is mandatory: 600-900 words
- Original commentary and analysis — do NOT rewrite a press release
- Explain why the news matters with concrete examples
- Conversational, not robotic
- No repeated phrases
- No generic filler like "in today's video" or "without further ado"
- Short sentences for retention
"""


def _expand_long_script(
    llm,
    title: str,
    url: str,
    research_context: str,
    scripts: GeneratedScripts,
) -> GeneratedScripts:
    current_words = _count_words(scripts.script_long)
    prompt = f"""Expand this YouTube long-form tech news script to 600-900 words.

Story: {title}
Source: {url}
Research:
{research_context}

Current script ({current_words} words — too short):
{scripts.script_long[:3000]}

Return JSON:
{{
  "script_sections": [
    {{"label": "Hook", "text": "..."}},
    {{"label": "Problem", "text": "..."}},
    {{"label": "What Happened", "text": "..."}},
    {{"label": "Why It Matters", "text": "..."}},
    {{"label": "Industry Impact", "text": "..."}},
    {{"label": "Future Outlook", "text": "..."}},
    {{"label": "Call To Action", "text": "..."}}
  ],
  "script_long": "Expanded narration. MUST be 600-900 words total."
}}

Rules:
- Keep facts accurate — do not invent quotes or numbers
- Add depth: industry context, comparisons, implications for developers and startups
- Minimum {MIN_LONG_SCRIPT_WORDS} words in script_long
"""
    result = llm.call_json(prompt)
    expanded_sections = result.get("script_sections", scripts.script_sections)
    script_long = result.get("script_long", "") or _combine_sections(expanded_sections)
    combined_long = max([script_long, _combine_sections(expanded_sections)], key=_count_words)

    return GeneratedScripts(
        script_short=scripts.script_short,
        script_long=combined_long,
        outline=scripts.outline,
        script_sections=expanded_sections or scripts.script_sections,
        script_short_sections=scripts.script_short_sections,
    )


def _build_scripts_from_result(result: dict, url: str) -> GeneratedScripts:
    script_sections = result.get("script_sections", [])
    script_short_sections = result.get("script_short_sections", [])
    script_long = result.get("script_long", "") or _combine_sections(script_sections)
    combined_long = max([script_long, _combine_sections(script_sections)], key=_count_words)

    return GeneratedScripts(
        script_short=result.get("script_short", "") or _combine_sections(script_short_sections),
        script_long=combined_long,
        outline=result.get("outline", {}),
        script_sections=script_sections,
        script_short_sections=script_short_sections,
    )


def _combine_sections(sections: list[dict[str, str]]) -> str:
    narration_parts = []
    for section in sections:
        section_text = str(section.get("text", "")).strip()
        if section_text:
            narration_parts.append(section_text)
    return "\n\n".join(narration_parts)


def _count_words(text: str) -> int:
    return len(text.split())


def _persist_scripts(scripts: GeneratedScripts, output_dir: Path, title: str) -> None:
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
    logger.info(
        "Scripts generated for: %s (long=%d words, short=%d words)",
        title[:60],
        _count_words(scripts.script_long),
        _count_words(scripts.script_short),
    )
