"""Resolve fonts and ffmpeg filter availability across CI and local machines."""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


@lru_cache(maxsize=1)
def ffmpeg_supports_filter(filter_name: str) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    return filter_name in output


def resolve_drawtext_font_path() -> str | None:
    for font_path in FONT_CANDIDATES:
        if Path(font_path).exists():
            return font_path
    return None


def escape_ffmpeg_path(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", "/")
    escaped = escaped.replace(":", r"\:")
    escaped = escaped.replace("'", r"\'")
    return escaped
