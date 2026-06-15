"""Video engine — multi-image Ken Burns, crossfades, and styled subtitles."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from futuredecoded.config.channel_profile import LONG_FORM_SPEC, SHORTS_SPEC
from futuredecoded.media.scene_planner import VideoScene, plan_video_scenes
from futuredecoded.media.audio_utils import get_audio_duration
from futuredecoded.media.watermark_engine import apply_watermark_to_video

logger = logging.getLogger("futuredecoded.media.video")

FRAMES_PER_SECOND = 25
FADE_DURATION_SECONDS = 0.6
SUBTITLE_STYLE = (
    "FontName=DejaVu Sans Bold,"
    "FontSize=28,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "Outline=2,"
    "Shadow=1,"
    "MarginV=70,"
    "Alignment=2,"
    "Bold=1"
)


def build_long_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    srt_path: Path | None = None,
    sections: list[dict[str, str]] | None = None,
) -> Path | None:
    return _build_video(
        script_text=script_text,
        audio_path=audio_path,
        images=images,
        output_path=output_path,
        width=LONG_FORM_SPEC.width,
        height=LONG_FORM_SPEC.height,
        srt_path=srt_path,
        sections=sections,
    )


def build_short_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    srt_path: Path | None = None,
    sections: list[dict[str, str]] | None = None,
) -> Path | None:
    return _build_video(
        script_text=script_text,
        audio_path=audio_path,
        images=images[:4],
        output_path=output_path,
        width=SHORTS_SPEC.width,
        height=SHORTS_SPEC.height,
        srt_path=srt_path,
        sections=sections,
    )


def _build_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    width: int,
    height: int,
    srt_path: Path | None,
    sections: list[dict[str, str]] | None = None,
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
        temp_path = Path(temp_dir)
        raw_video = temp_path / "raw.mp4"
        if sections:
            scenes = plan_video_scenes(sections, duration, script_text[:80], images)
            segment_clips = _render_scene_segments(scenes, width, height, temp_path)
        else:
            segment_clips = _render_image_segments(images, duration, width, height, temp_path)
        if not segment_clips:
            logger.error("Failed to render image segments")
            return None

        if not _concatenate_video_segments(segment_clips, raw_video):
            logger.error("Failed to concatenate image segments")
            return None

        if not _mux_audio(raw_video, audio_path, temp_path / "with_audio.mp4", duration):
            logger.error("Failed to mux audio")
            return None

        final_source = temp_path / "with_audio.mp4"
        if _finalize_video(final_source, output_path, srt_path, width, height):
            logger.info("Video finalized with watermark/subtitles: %s", output_path.name)
        else:
            shutil.copy(final_source, output_path)

    if not output_path.exists():
        return None

    logger.info("Video built: %s (%.1fMB)", output_path.name, output_path.stat().st_size / 1024 / 1024)
    return output_path


def _render_scene_segments(
    scenes: list[VideoScene],
    width: int,
    height: int,
    temp_dir: Path,
) -> list[Path]:
    clip_paths: list[Path] = []
    for index, scene in enumerate(scenes):
        image_path = scene.image_path
        if not image_path or not image_path.exists():
            continue
        clip_path = temp_dir / f"scene_{index:02d}.mp4"
        segment_duration = max(scene.duration_seconds, 3.0)
        if _render_single_segment(image_path, clip_path, segment_duration, index, width, height):
            clip_paths.append(clip_path)
    return clip_paths


def _render_image_segments(
    images: list[Path],
    duration: float,
    width: int,
    height: int,
    temp_dir: Path,
) -> list[Path]:
    usable_images = [image for image in images if image.exists()]
    if not usable_images:
        return []

    target_scene_count = max(3, int(duration / 4.0))
    segment_duration = max(min(duration / target_scene_count, 5.0), 3.0)
    clip_paths: list[Path] = []

    for index, image in enumerate(usable_images):
        clip_path = temp_dir / f"segment_{index:02d}.mp4"
        if _render_single_segment(image, clip_path, segment_duration, index, width, height):
            clip_paths.append(clip_path)

    return clip_paths


def _render_single_segment(
    image: Path,
    clip_path: Path,
    segment_duration: float,
    index: int,
    width: int,
    height: int,
) -> bool:
    frame_count = max(int(segment_duration * FRAMES_PER_SECOND), FRAMES_PER_SECOND * 3)
    zoom_filter = _build_zoompan_filter(index, frame_count, width, height)
    fade_out_start = max(0.0, segment_duration - FADE_DURATION_SECONDS)
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"{zoom_filter},"
        f"eq=contrast=1.08:saturation=1.15:brightness=0.02,"
        f"vignette=angle=PI/5,"
        f"fade=t=in:st=0:d={FADE_DURATION_SECONDS},"
        f"fade=t=out:st={fade_out_start:.2f}:d={FADE_DURATION_SECONDS},"
        f"fps={FRAMES_PER_SECOND}"
    )
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image),
        "-t",
        f"{segment_duration:.2f}",
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(clip_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.warning("Segment render failed for %s: %s", image.name, result.stderr[-200:])
        return False
    return True


def _build_zoompan_filter(index: int, frame_count: int, width: int, height: int) -> str:
    if index % 2 == 0:
        zoom_expression = "min(zoom+0.0012,1.18)"
    else:
        zoom_expression = "if(lte(zoom,1.0),1.18,max(1.001,zoom-0.0012))"
    return (
        f"zoompan=z='{zoom_expression}':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}"
    )


def _concatenate_video_segments(segment_clips: list[Path], output_path: Path) -> bool:
    concat_list_path = output_path.parent / "concat_list.txt"
    concat_list_path.write_text(
        "\n".join(f"file '{clip}'" for clip in segment_clips),
        encoding="utf-8",
    )
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error("Concat failed: %s", result.stderr[-300:])
        return False
    return True


def _mux_audio(video_path: Path, audio_path: Path, output_path: Path, duration: float) -> bool:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        "-t",
        str(min(duration, 600)),
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error("Audio mux failed: %s", result.stderr[-300:])
        return False
    return True


def _finalize_video(
    video_path: Path,
    output_path: Path,
    srt_path: Path | None,
    width: int,
    height: int,
) -> bool:
    if apply_watermark_to_video(video_path, output_path, width, height, srt_path=srt_path):
        return True
    if srt_path and srt_path.exists():
        return _burn_subtitles(video_path, srt_path, output_path)
    return False


def _burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> bool:
    srt_escaped = str(srt_path).replace(":", r"\:")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"subtitles={srt_escaped}:force_style='{SUBTITLE_STYLE}'",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.warning("Subtitle burn failed: %s", result.stderr[-200:])
        return False
    return True
