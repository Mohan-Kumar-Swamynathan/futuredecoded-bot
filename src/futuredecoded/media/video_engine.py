"""Video engine — ffmpeg Ken Burns + subtitles for long and short formats."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from futuredecoded.config.channel_profile import LONG_FORM_SPEC, SHORTS_SPEC
from futuredecoded.media.voice_engine import get_audio_duration

logger = logging.getLogger("futuredecoded.media.video")


def build_long_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    srt_path: Path | None = None,
) -> Path | None:
    return _build_video(
        script_text=script_text,
        audio_path=audio_path,
        images=images,
        output_path=output_path,
        width=LONG_FORM_SPEC.width,
        height=LONG_FORM_SPEC.height,
        srt_path=srt_path,
    )


def build_short_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    srt_path: Path | None = None,
) -> Path | None:
    return _build_video(
        script_text=script_text,
        audio_path=audio_path,
        images=images[:4],
        output_path=output_path,
        width=SHORTS_SPEC.width,
        height=SHORTS_SPEC.height,
        srt_path=srt_path,
    )


def _build_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    width: int,
    height: int,
    srt_path: Path | None,
) -> Path | None:
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found")
        return None
    if not images:
        logger.error("No images for video")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = get_audio_duration(audio_path)
    if duration < 5:
        logger.error("Audio too short: %.1fs", duration)
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        raw_video = Path(temp_dir) / "raw.mp4"
        image = images[0]
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image),
            "-i", str(audio_path),
            "-vf", (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                "zoompan=z='min(zoom+0.001,1.15)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s="
                f"{width}x{height},"
                f"fps=25"
            ),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-c:a", "aac", "-shortest",
            "-t", str(min(duration, 600)),
            str(raw_video),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            logger.error("Video encode failed: %s", result.stderr[-300:])
            return None

        if srt_path and srt_path.exists():
            srt_escaped = str(srt_path).replace(":", r"\:")
            final_cmd = [
                "ffmpeg", "-y", "-i", str(raw_video),
                "-vf", f"subtitles={srt_escaped}:force_style='FontSize=24,PrimaryColour=&HFFFFFF'",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "copy",
                str(output_path),
            ]
            sub_result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=600)
            if sub_result.returncode != 0:
                shutil.copy(raw_video, output_path)
        else:
            shutil.copy(raw_video, output_path)

    logger.info("Video built: %s (%.1fMB)", output_path.name, output_path.stat().st_size / 1024 / 1024)
    return output_path
