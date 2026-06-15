"""Shared audio utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
