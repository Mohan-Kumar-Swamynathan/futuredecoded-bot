"""Text overlay helpers for hook scenes and key statistics."""

from __future__ import annotations

import re


def escape_drawtext_text(text: str) -> str:
    cleaned = text.upper().strip()
    cleaned = cleaned.replace("\\", "\\\\")
    cleaned = cleaned.replace(":", r"\:")
    cleaned = cleaned.replace("'", r"\'")
    cleaned = cleaned.replace("%", r"\%")
    return cleaned[:32]


def build_overlay_drawtext_filter(
    overlay_text: str,
    width: int,
    height: int,
    is_hook_scene: bool = False,
) -> str:
    if not overlay_text.strip():
        return ""

    escaped_text = escape_drawtext_text(overlay_text)
    font_size = 64 if is_hook_scene else 48
    y_position = int(height * 0.12) if height > width else int(height * 0.16)

    return (
        f"drawtext=text='{escaped_text}':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"fontsize={font_size}:fontcolor=white:"
        f"box=1:boxcolor=black@0.55:boxborderw=18:"
        f"x=(w-text_w)/2:y={y_position}"
    )


def extract_retention_overlay(section_text: str, scene_index: int) -> str | None:
    if scene_index % 6 != 0:
        return None
    question_match = re.search(r"(\bWill\b[^?.!]{0,60}[?])", section_text)
    if question_match:
        return question_match.group(1).upper()[:32]
    return None
