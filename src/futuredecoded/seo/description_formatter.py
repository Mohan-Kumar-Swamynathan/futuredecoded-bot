"""YouTube description formatter — real newlines, chapters, and sources."""

from __future__ import annotations

import re

from futuredecoded.config.channel_profile import CHANNEL_NAME, CHANNEL_TAGLINE
from futuredecoded.seo.chapter_builder import VideoChapter

DEFAULT_CTA = (
    "👍 Like this video if it helped you stay ahead of AI and tech news.\n"
    "🔔 Subscribe to FutureDecoded for daily breakdowns — Making Sense of Tomorrow."
)


def normalize_multiline_text(text: str) -> str:
    normalized = str(text or "")
    normalized = normalized.replace("\\n", "\n").replace("\\t", "\t")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _format_source_line(source: str) -> str:
    source_text = normalize_multiline_text(source)
    if source_text.startswith("http"):
        return f"• {source_text}"
    return f"• {source_text}"


def build_long_form_description(
    intro: str,
    key_points: list[str],
    chapters: list[VideoChapter],
    sources: list[str],
    hashtags: list[str] | None = None,
    cta: str = DEFAULT_CTA,
) -> str:
    lines: list[str] = [
        normalize_multiline_text(intro),
        "",
        "📌 Key Points",
    ]

    for point in key_points:
        cleaned_point = normalize_multiline_text(point)
        if cleaned_point:
            lines.append(f"• {cleaned_point}")

    if chapters:
        lines.extend(["", "⏱ Chapters"])
        for chapter in chapters:
            lines.append(f"{chapter.time} {chapter.label}")

    if sources:
        lines.extend(["", "🔗 Sources"])
        lines.extend(_format_source_line(source) for source in sources[:5])

    lines.extend(["", normalize_multiline_text(cta)])

    tag_line = " ".join(hashtags or ["#AI", "#TechNews", "#FutureDecoded"])
    lines.extend(["", tag_line, "", f"{CHANNEL_NAME} — {CHANNEL_TAGLINE}"])

    description = "\n".join(line for line in lines if line is not None)
    return description[:5000]


def build_shorts_description(
    hook: str,
    key_points: list[str],
    sources: list[str],
    hashtags: list[str] | None = None,
    chapters: list[VideoChapter] | None = None,
) -> str:
    lines: list[str] = [
        normalize_multiline_text(hook),
        "",
        "📌 In this Short",
    ]

    for point in key_points[:4]:
        cleaned_point = normalize_multiline_text(point)
        if cleaned_point:
            lines.append(f"• {cleaned_point}")

    if chapters:
        lines.extend(["", "⏱ Chapters"])
        for chapter in chapters:
            lines.append(f"{chapter.time} {chapter.label}")

    if sources:
        lines.extend(["", "🔗 Sources"])
        lines.extend(_format_source_line(source) for source in sources[:3])

    tag_line = " ".join(hashtags or ["#Shorts", "#AI", "#TechNews"])
    lines.extend(["", tag_line, "", f"{CHANNEL_NAME} — {CHANNEL_TAGLINE}"])

    return "\n".join(lines)[:5000]
