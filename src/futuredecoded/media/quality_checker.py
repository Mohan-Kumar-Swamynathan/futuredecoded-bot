"""Pre-export quality checks for FutureDecoded videos."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.media.scene_planner import MAX_SCENE_DURATION_SECONDS
from futuredecoded.media.video_export_settings import require_burned_captions, run_black_frame_detection

logger = logging.getLogger("futuredecoded.media.quality")


@dataclass
class QualityReport:
    passed: bool
    issues: list[str]


def validate_video_output(
    video_path: Path,
    caption_path: Path | None,
    scene_durations: list[float],
) -> QualityReport:
    issues: list[str] = []

    if not video_path.exists() or video_path.stat().st_size == 0:
        issues.append("Video file missing or empty")

    if require_burned_captions() and caption_path is not None and not caption_path.exists():
        issues.append("Captions missing")

    for index, duration in enumerate(scene_durations):
        if duration > MAX_SCENE_DURATION_SECONDS + 0.01:
            issues.append(f"Scene {index + 1} exceeds 5 seconds ({duration:.1f}s)")

    if video_path.exists() and not _has_audio_stream(video_path):
        issues.append("Video has no audio stream")

    if video_path.exists() and run_black_frame_detection() and _detect_black_frames(video_path):
        issues.append("Potential black frames detected")

    passed = len(issues) == 0
    if not passed:
        logger.warning("Video quality checks: %s", "; ".join(issues[:4]))
    else:
        logger.info("Video quality checks passed")
    return QualityReport(passed=passed, issues=issues)


def _has_audio_stream(video_path: Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return "audio" in result.stdout


def _detect_black_frames(video_path: Path) -> bool:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            "blackdetect=d=0.35:pix_th=0.10",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return "black_start" in result.stderr
