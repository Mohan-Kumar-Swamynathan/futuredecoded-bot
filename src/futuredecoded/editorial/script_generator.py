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
    points = research.summary_points[:8]
    return "\n".join(f"- {point}" for point in points)


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

Research context (use these facts, add your own analysis):
{research_context}
{strictness}

CHANNEL VOICE — this is critical:
FutureDecoded speaks like a sharp, opinionated tech analyst — not a news anchor reading a teleprompter.
Think: the smartest engineer at the company who also happens to explain things really well.
- Direct, confident opinions ("This is a big deal because...", "Here's what most people are missing...")
- Concrete comparisons and numbers — never vague ("3x faster than GPT-4", "saves 40 hours per week")
- Conversational but authoritative — short punchy sentences followed by one longer explanation
- Speak TO the viewer, not AT them — "you", "your workflow", "if you're building with this"

AUDIENCE: Developers, AI engineers, startup founders, tech enthusiasts — people who BUILD things.
They want: what changed, why it matters for their work, what they should do about it.

Return JSON:
{{
  "outline": {{
    "hook": "...",
    "key_facts": ["...", "..."],
    "impact": "...",
    "sources": ["{url}"]
  }},
  "script_sections": [
    {{"label": "Hook", "text": "15-second spoken hook. Start with the most surprising fact or a counterintuitive statement. NEVER start with 'Today', 'In this video', 'Welcome'. Open on the idea itself. (~35 words)"}},
    {{"label": "Context", "text": "Why this matters RIGHT NOW. What problem does this solve or what shift does it signal? (~90 words)"}},
    {{"label": "What Happened", "text": "The actual news — concrete facts, numbers, dates, who did what. (~100 words)"}},
    {{"label": "Technical Depth", "text": "How it actually works — one specific technical insight that a developer would appreciate. Avoid hand-waving. (~100 words)"}},
    {{"label": "Industry Impact", "text": "Who wins, who loses, what changes in the next 6-12 months. Specific companies or workflows named. (~100 words)"}},
    {{"label": "Your Take", "text": "A direct opinion: is this overhyped, underrated, or exactly what it claims? Why? (~80 words)"}},
    {{"label": "Call To Action", "text": "End with a comment-driving question — two concrete options, not open-ended. (~30 words)"}}
  ],
  "script_short_sections": [
    {{"label": "Hook", "text": "First 3 seconds — one shocking number or counterintuitive fact. No greeting."}},
    {{"label": "The News", "text": "What happened in one sentence."}},
    {{"label": "Why It Matters", "text": "One sentence — what changes for developers or builders."}},
    {{"label": "CTA", "text": "Subscribe + one question."}}
  ],
  "script_short": "45-60 second Shorts narration. 90-120 words. Fast, punchy, one key insight, ends with question.",
  "script_long": "Full 4-6 minute narration. MUST be 600-900 words. Combine all sections into flowing speech — no section headers."
}}

HARD RULES:
- script_long word count is mandatory: 600-900 words
- No repeated phrases or padding
- No generic openers: 'In today's video', 'without further ado', 'that's right folks'
- Every claim needs a concrete number or named example — no vague 'significant improvement'
- The 'Your Take' section must have a clear opinion, not a fence-sit
- Last sentence of script_long must be a two-choice question that forces a comment
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
    {{"label": "Context", "text": "..."}},
    {{"label": "What Happened", "text": "..."}},
    {{"label": "Technical Depth", "text": "..."}},
    {{"label": "Industry Impact", "text": "..."}},
    {{"label": "Your Take", "text": "..."}},
    {{"label": "Call To Action", "text": "..."}}
  ],
  "script_long": "Expanded narration. MUST be 600-900 words total."
}}

Rules:
- Keep facts accurate — do not invent quotes or numbers
- Add depth: technical insight, developer implications, who wins/loses
- Direct opinions allowed and encouraged in 'Your Take'
- Minimum {MIN_LONG_SCRIPT_WORDS} words in script_long
- End with a two-choice comment question
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
