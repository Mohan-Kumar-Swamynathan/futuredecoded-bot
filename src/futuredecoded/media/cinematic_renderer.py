"""Cinematic renderer — fullscreen stock video with bottom English subtitles."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from futuredecoded.media.caption_engine import WordTiming, build_scene_ass_subtitles
from futuredecoded.media.font_resolver import escape_ffmpeg_path, ffmpeg_supports_filter, resolve_drawtext_font_path
from futuredecoded.media.stock_video_collector import probe_video_duration, validate_stock_video_clip
from futuredecoded.media.video_export_settings import (
    ffmpeg_crf,
    ffmpeg_preset,
    ffmpeg_thread_count,
    segment_render_timeout_seconds,
)

logger = logging.getLogger(__name__)


def load_word_timings(word_timing_path: Path) -> list[WordTiming]:
    if not word_timing_path.exists():
        return []
    payload = json.loads(word_timing_path.read_text(encoding="utf-8"))
    return [
        WordTiming(
            start_seconds=float(item["start_seconds"]),
            end_seconds=float(item["end_seconds"]),
            text=str(item["text"]),
        )
        for item in payload
    ]


def render_cinematic_scene_clip(
    stock_video_path: Path,
    clip_path: Path,
    scene_duration_seconds: float,
    scene_start_seconds: float,
    word_timings: list[WordTiming],
    section_label: str,
    width: int,
    height: int,
) -> bool:
    """Render one scene clip with stock footage and word-synced bottom subtitles."""
    if not validate_stock_video_clip(stock_video_path):
        logger.warning("Invalid stock clip for cinematic scene: %s", stock_video_path)
        return False

    if _render_cinematic_scene_with_ffmpeg(
        stock_video_path=stock_video_path,
        clip_path=clip_path,
        scene_duration_seconds=scene_duration_seconds,
        scene_start_seconds=scene_start_seconds,
        word_timings=word_timings,
        section_label=section_label,
        width=width,
        height=height,
        include_subtitles=True,
    ):
        return True

    logger.warning("Cinematic ASS burn failed — retrying stock video without subtitles")
    return _render_cinematic_scene_with_ffmpeg(
        stock_video_path=stock_video_path,
        clip_path=clip_path,
        scene_duration_seconds=scene_duration_seconds,
        scene_start_seconds=scene_start_seconds,
        word_timings=word_timings,
        section_label=section_label,
        width=width,
        height=height,
        include_subtitles=False,
    )


def _render_cinematic_scene_with_ffmpeg(
    stock_video_path: Path,
    clip_path: Path,
    scene_duration_seconds: float,
    scene_start_seconds: float,
    word_timings: list[WordTiming],
    section_label: str,
    width: int,
    height: int,
    include_subtitles: bool,
) -> bool:
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = clip_path.with_suffix(".ass")
    filter_chain = _build_video_filter_chain(
        width=width,
        height=height,
        ass_path=ass_path,
        section_label=section_label,
        scene_start_seconds=scene_start_seconds,
        scene_duration_seconds=scene_duration_seconds,
        word_timings=word_timings,
        include_subtitles=include_subtitles,
    )
    if filter_chain is None:
        return False

    stock_duration = probe_video_duration(stock_video_path)
    stream_loop = "-1" if stock_duration < scene_duration_seconds else "0"
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-stream_loop",
        stream_loop,
        "-i",
        str(stock_video_path),
        "-t",
        f"{scene_duration_seconds:.3f}",
        "-vf",
        filter_chain,
        "-c:v",
        "libx264",
        "-preset",
        ffmpeg_preset(),
        "-crf",
        ffmpeg_crf(),
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(clip_path),
    ]
    command = _append_thread_args(command)
    result = subprocess.run(command, capture_output=True, text=True, timeout=segment_render_timeout_seconds())
    if result.returncode != 0:
        logger.warning(
            "Cinematic ffmpeg failed (subs=%s): %s",
            include_subtitles,
            result.stderr[-400:],
        )
        return False
    return clip_path.exists() and clip_path.stat().st_size > 10_000


def _build_video_filter_chain(
    width: int,
    height: int,
    ass_path: Path,
    section_label: str,
    scene_start_seconds: float,
    scene_duration_seconds: float,
    word_timings: list[WordTiming],
    include_subtitles: bool,
) -> str | None:
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "eq=contrast=1.05:saturation=1.08",
    ]

    if include_subtitles and word_timings and ffmpeg_supports_filter("ass"):
        build_scene_ass_subtitles(
            word_timings,
            scene_start_seconds,
            scene_duration_seconds,
            ass_path,
            play_res_x=width,
            play_res_y=height,
        )
        if ass_path.exists() and ass_path.stat().st_size > 0:
            escaped_ass = escape_ffmpeg_path(ass_path)
            filters.append(f"ass='{escaped_ass}'")

    section_filter = _build_section_label_filter(section_label, width)
    if section_filter:
        filters.append(section_filter)

    return ",".join(filters) if filters else None


def _build_section_label_filter(section_label: str, width: int) -> str | None:
    if not ffmpeg_supports_filter("drawtext"):
        return None

    label = _sanitize_drawtext(section_label.strip()[:42])
    if not label:
        return None

    font_path = resolve_drawtext_font_path()
    font_size = 28 if width >= 1600 else 22
    if font_path:
        escaped_font = escape_ffmpeg_path(Path(font_path))
        return (
            f"drawtext=fontfile='{escaped_font}':text='{label}':fontsize={font_size}:"
            "fontcolor=white:x=40:y=36:box=1:boxcolor=black@0.55:boxborderw=12"
        )
    return (
        f"drawtext=text='{label}':fontsize={font_size}:"
        "fontcolor=white:x=40:y=36:box=1:boxcolor=black@0.55:boxborderw=12"
    )


def _sanitize_drawtext(text: str) -> str:
    cleaned = text.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    cleaned = re.sub(r"[^\w\s\-&.,!?'\"]+", "", cleaned)
    return cleaned.strip()


def _append_thread_args(command: list[str]) -> list[str]:
    thread_count = ffmpeg_thread_count()
    if thread_count <= 0:
        return command
    return command[:1] + ["-threads", str(thread_count)] + command[1:]


def _count_visible_words(word_timings: list[WordTiming], global_time: float) -> int:
    visible = 0
    for timing in word_timings:
        if timing.end_seconds <= global_time + 0.04:
            visible += 1
        else:
            break
    return visible
