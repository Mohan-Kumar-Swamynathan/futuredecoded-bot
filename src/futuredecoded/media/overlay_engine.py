"""Text overlay helpers for hook scenes and key statistics."""

from __future__ import annotations

import re

from futuredecoded.media.font_resolver import ffmpeg_supports_filter, resolve_drawtext_font_path


def escape_drawtext_text(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 $%+\-]", " ", text.upper()).strip()
    cleaned = cleaned.replace("\\", "\\\\")
    cleaned = cleaned.replace(":", r"\:")
    cleaned = cleaned.replace("'", r"\'")
    cleaned = cleaned.replace("%", r"\%")
    cleaned = cleaned.replace(",", " ")
    return cleaned[:32]


def is_drawtext_available() -> bool:
    return ffmpeg_supports_filter("drawtext")


def build_overlay_drawtext_filter(
    overlay_text: str,
    width: int,
    height: int,
    is_hook_scene: bool = False,
) -> str:
    if not overlay_text.strip() or not is_drawtext_available():
        return ""

    escaped_text = escape_drawtext_text(overlay_text)
    if not escaped_text:
        return ""

    font_size = 64 if is_hook_scene else 48
    y_position = int(height * 0.12) if height > width else int(height * 0.16)
    font_path = resolve_drawtext_font_path()

    font_clause = f"fontfile={font_path}:" if font_path else ""
    return (
        f"drawtext=text='{escaped_text}':"
        f"{font_clause}"
        f"fontsize={font_size}:fontcolor=white:"
        f"box=1:boxcolor=black@0.55:boxborderw=18:"
        f"x=(w-text_w)/2:y={y_position}"
    )
