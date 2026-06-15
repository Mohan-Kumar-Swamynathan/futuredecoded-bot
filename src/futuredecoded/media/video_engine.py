"""Video engine — documentary-style motion, overlays, captions, 30fps export."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from futuredecoded.config.channel_profile import LONG_FORM_SPEC, SHORTS_SPEC
from futuredecoded.media.audio_utils import get_audio_duration
from futuredecoded.media.font_resolver import escape_ffmpeg_path
from futuredecoded.media.overlay_engine import build_overlay_drawtext_filter
from futuredecoded.media.quality_checker import validate_video_output
from futuredecoded.media.scene_planner import VideoScene, export_scene_manifest, plan_video_scenes
from futuredecoded.media.video_export_settings import (
    export_fps,
    ffmpeg_crf,
    ffmpeg_preset,
    ffmpeg_thread_count,
    finalize_render_timeout_seconds,
    is_ci_build,
    segment_render_timeout_seconds,
    use_lightweight_motion,
)
from futuredecoded.media.watermark_engine import apply_watermark_to_video

logger = logging.getLogger("futuredecoded.media.video")

FADE_DURATION_SECONDS = 0.45
AUDIO_BITRATE = "192k"


def build_long_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    caption_path: Path | None = None,
    sections: list[dict[str, str]] | None = None,
    story_title: str = "",
) -> Path | None:
    return _build_video(
        script_text=script_text,
        audio_path=audio_path,
        images=images,
        output_path=output_path,
        width=LONG_FORM_SPEC.width,
        height=LONG_FORM_SPEC.height,
        caption_path=caption_path,
        sections=sections,
        story_title=story_title or script_text[:80],
    )


def build_short_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    caption_path: Path | None = None,
    sections: list[dict[str, str]] | None = None,
    story_title: str = "",
) -> Path | None:
    return _build_video(
        script_text=script_text,
        audio_path=audio_path,
        images=images[:6],
        output_path=output_path,
        width=SHORTS_SPEC.width,
        height=SHORTS_SPEC.height,
        caption_path=caption_path,
        sections=sections,
        story_title=story_title or script_text[:80],
    )


def _build_video(
    script_text: str,
    audio_path: Path,
    images: list[Path],
    output_path: Path,
    width: int,
    height: int,
    caption_path: Path | None,
    sections: list[dict[str, str]] | None = None,
    story_title: str = "",
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

    resolved_caption_path = _resolve_caption_path(caption_path, audio_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        raw_video = temp_path / "raw.mp4"
        scenes = plan_video_scenes(
            sections or [{"label": "Story", "text": script_text}],
            duration,
            story_title,
            images,
        )
        export_scene_manifest(scenes, output_path.parent / "scene_manifest.json")
        logger.info(
            "Rendering %d scenes for %s (%.1fs, ci=%s, fps=%d, lightweight=%s)",
            len(scenes),
            output_path.name,
            duration,
            is_ci_build(),
            export_fps(),
            use_lightweight_motion(),
        )
        segment_clips = _render_scene_segments(scenes, width, height, temp_path)
        if not segment_clips:
            logger.error("Failed to render image segments")
            return None

        if not _concatenate_video_segments(segment_clips, raw_video):
            logger.error("Failed to concatenate image segments")
            return None

        with_audio = temp_path / "with_audio.mp4"
        if not _mux_audio(raw_video, audio_path, with_audio, duration):
            logger.error("Failed to mux audio")
            return None

        if _finalize_video(with_audio, output_path, resolved_caption_path, width, height):
            logger.info("Video finalized with watermark/captions: %s", output_path.name)
        else:
            shutil.copy(with_audio, output_path)

    if not output_path.exists():
        return None

    quality_report = validate_video_output(
        output_path,
        resolved_caption_path,
        [scene.duration_seconds for scene in scenes],
    )
    if not quality_report.passed:
        logger.warning("Export completed with quality warnings: %s", "; ".join(quality_report.issues[:3]))

    logger.info("Video built: %s (%.1fMB)", output_path.name, output_path.stat().st_size / 1024 / 1024)
    return output_path


def _resolve_caption_path(caption_path: Path | None, audio_path: Path) -> Path | None:
    if caption_path and caption_path.exists():
        return caption_path
    ass_candidate = audio_path.with_suffix(".ass")
    if ass_candidate.exists():
        return ass_candidate
    srt_candidate = audio_path.with_suffix(".srt")
    if srt_candidate.exists():
        return srt_candidate
    return caption_path


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
        logger.info(
            "Rendering scene %d/%d (%.1fs, %s)",
            index + 1,
            len(scenes),
            scene.duration_seconds,
            scene.animation_type,
        )
        if _render_single_segment(
            image_path=image_path,
            clip_path=clip_path,
            segment_duration=scene.duration_seconds,
            animation_type=scene.animation_type,
            overlay_text=scene.text_overlay,
            is_hook_scene=scene.is_hook_scene,
            width=width,
            height=height,
        ):
            clip_paths.append(clip_path)
    return clip_paths


def _render_single_segment(
    image_path: Path,
    clip_path: Path,
    segment_duration: float,
    animation_type: str,
    overlay_text: str | None,
    is_hook_scene: bool,
    width: int,
    height: int,
) -> bool:
    if _render_segment_with_ffmpeg(
        image_path,
        clip_path,
        segment_duration,
        animation_type,
        overlay_text,
        is_hook_scene,
        width,
        height,
    ):
        return True

    if overlay_text:
        logger.warning("Segment render failed with overlay — retrying without text overlay")
        return _render_segment_with_ffmpeg(
            image_path,
            clip_path,
            segment_duration,
            animation_type,
            overlay_text=None,
            is_hook_scene=False,
            width=width,
            height=height,
        )
    return False


def _render_segment_with_ffmpeg(
    image_path: Path,
    clip_path: Path,
    segment_duration: float,
    animation_type: str,
    overlay_text: str | None,
    is_hook_scene: bool,
    width: int,
    height: int,
) -> bool:
    frame_count = max(int(segment_duration * export_fps()), export_fps() * 3)
    motion_filter = None if use_lightweight_motion() else _build_motion_filter(
        animation_type,
        frame_count,
        width,
        height,
    )
    fade_out_start = max(0.0, segment_duration - FADE_DURATION_SECONDS)
    filter_parts = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "eq=contrast=1.10:saturation=1.18:brightness=0.02",
        "vignette=angle=PI/5",
        f"fade=t=in:st=0:d={FADE_DURATION_SECONDS}",
        f"fade=t=out:st={fade_out_start:.2f}:d={FADE_DURATION_SECONDS}",
    ]
    if motion_filter:
        filter_parts.insert(2, motion_filter)

    overlay_filter = build_overlay_drawtext_filter(
        overlay_text or "",
        width=width,
        height=height,
        is_hook_scene=is_hook_scene,
    )
    if overlay_filter:
        filter_parts.append(overlay_filter)

    filter_parts.append(f"fps={export_fps()}")
    video_filter = ",".join(filter_parts)

    command = _append_ffmpeg_thread_args(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{segment_duration:.2f}",
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            ffmpeg_preset(),
            "-crf",
            ffmpeg_crf(),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(export_fps()),
            str(clip_path),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=segment_render_timeout_seconds())
    if result.returncode != 0:
        logger.warning("Segment render failed for %s: %s", image_path.name, result.stderr[-200:])
        return False
    return True


def _build_motion_filter(animation_type: str, frame_count: int, width: int, height: int) -> str:
    if animation_type == "zoom_out":
        zoom_expression = "if(lte(zoom,1.0),1.20,max(1.001,zoom-0.0015))"
        pan_x = "iw/2-(iw/zoom/2)"
    elif animation_type == "pan_left":
        zoom_expression = "1.18"
        pan_x = f"(iw-(iw/zoom))*on/{frame_count}"
    elif animation_type == "pan_right":
        zoom_expression = "1.18"
        pan_x = f"(iw-(iw/zoom))*(1-on/{frame_count})"
    else:
        zoom_expression = "min(zoom+0.0015,1.20)"
        pan_x = "iw/2-(iw/zoom/2)"

    return (
        f"zoompan=z='{zoom_expression}':d={frame_count}:"
        f"x='{pan_x}':y='ih/2-(ih/zoom/2)':s={width}x{height}"
    )


def _concatenate_video_segments(segment_clips: list[Path], output_path: Path) -> bool:
    concat_list_path = output_path.parent / "concat_list.txt"
    concat_list_path.write_text(
        "\n".join(f"file '{clip}'" for clip in segment_clips),
        encoding="utf-8",
    )
    command = _append_ffmpeg_thread_args(
        [
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
            ffmpeg_preset(),
            "-crf",
            ffmpeg_crf(),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(export_fps()),
            str(output_path),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=finalize_render_timeout_seconds())
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
        "-b:a",
        AUDIO_BITRATE,
        "-shortest",
        "-t",
        str(min(duration, 600)),
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=finalize_render_timeout_seconds())
    if result.returncode != 0:
        logger.error("Audio mux failed: %s", result.stderr[-300:])
        return False
    return True


def _append_ffmpeg_thread_args(command: list[str]) -> list[str]:
    thread_count = ffmpeg_thread_count()
    if thread_count <= 0:
        return command
    return command[:1] + ["-threads", str(thread_count)] + command[1:]


def _finalize_video(
    video_path: Path,
    output_path: Path,
    caption_path: Path | None,
    width: int,
    height: int,
) -> bool:
    if apply_watermark_to_video(video_path, output_path, width, height, caption_path=caption_path):
        return True
    if caption_path and caption_path.exists():
        return _burn_captions(video_path, caption_path, output_path)
    return False


def _burn_captions(video_path: Path, caption_path: Path, output_path: Path) -> bool:
    escaped_path = escape_ffmpeg_path(caption_path)
    subtitle_style = (
        "FontName=DejaVu Sans Bold,FontSize=42,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=3,Shadow=1,MarginV=90,Alignment=2,Bold=1"
    )
    video_filter = f"subtitles='{escaped_path}':force_style='{subtitle_style}'"

    command = _append_ffmpeg_thread_args(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            ffmpeg_preset(),
            "-crf",
            ffmpeg_crf(),
            "-c:a",
            "copy",
            str(output_path),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=finalize_render_timeout_seconds())
    if result.returncode != 0:
        logger.warning("Caption burn failed: %s", result.stderr[-200:])
        return False
    return True
