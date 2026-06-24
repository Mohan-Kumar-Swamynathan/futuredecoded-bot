"""Cinematic renderer — fullscreen stock video with bottom English subtitles."""

from __future__ import annotations

import io
import json
import logging
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from futuredecoded.media.caption_engine import WordTiming
from futuredecoded.media.font_resolver import resolve_drawtext_font_path
from futuredecoded.media.stock_video_collector import probe_video_duration
from futuredecoded.media.video_export_settings import (
    export_fps,
    ffmpeg_crf,
    ffmpeg_preset,
    segment_render_timeout_seconds,
)

logger = logging.getLogger(__name__)

BOTTOM_GRADIENT_RATIO = 0.28


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
    fps = export_fps()
    frame_count = max(int(scene_duration_seconds * fps), fps)
    font_path = resolve_drawtext_font_path()
    font = _load_subtitle_font(width, font_path)
    narration_words = [timing.text for timing in word_timings]

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-t",
            f"{scene_duration_seconds:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            ffmpeg_preset(),
            "-crf",
            ffmpeg_crf(),
            "-pix_fmt",
            "yuv420p",
            str(clip_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        for frame_index in range(frame_count):
            local_time = frame_index / fps
            global_time = scene_start_seconds + local_time
            visible_word_count = _count_visible_words(word_timings, global_time)
            visual_progress = (local_time / max(scene_duration_seconds, 0.1)) % 1.0
            frame = _render_cinematic_frame(
                stock_video_path=stock_video_path,
                visual_progress=visual_progress,
                section_label=section_label,
                narration_words=narration_words,
                visible_word_count=visible_word_count,
                width=width,
                height=height,
                font=font,
            )
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        _, stderr = process.communicate(timeout=segment_render_timeout_seconds())
        if process.returncode != 0:
            logger.warning("Cinematic encode failed: %s", stderr.decode("utf-8", errors="ignore")[-300:])
            return False
        return clip_path.exists() and clip_path.stat().st_size > 0
    except Exception as exc:
        logger.warning("Cinematic render failed: %s", exc)
        process.kill()
        return False


def _count_visible_words(word_timings: list[WordTiming], global_time: float) -> int:
    visible = 0
    for timing in word_timings:
        if timing.end_seconds <= global_time + 0.04:
            visible += 1
        else:
            break
    return visible


def _render_cinematic_frame(
    stock_video_path: Path,
    visual_progress: float,
    section_label: str,
    narration_words: list[str],
    visible_word_count: int,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> Image.Image:
    base_frame = _extract_video_frame(stock_video_path, visual_progress, width, height)
    if base_frame is None:
        base_frame = Image.new("RGB", (width, height), (18, 24, 38))

    canvas = base_frame.convert("RGBA")
    canvas = Image.alpha_composite(canvas, _create_bottom_gradient_overlay(width, height))
    draw = ImageDraw.Draw(canvas)
    _draw_section_pill(draw, section_label, font)
    _draw_bottom_narration_text(draw, narration_words, visible_word_count, width, height, font)
    return canvas.convert("RGB")


def _extract_video_frame(
    video_path: Path,
    progress: float,
    width: int,
    height: int,
) -> Image.Image | None:
    if not video_path.exists():
        return None

    duration_seconds = probe_video_duration(video_path)
    if duration_seconds <= 0:
        return None

    timestamp = min(duration_seconds - 0.05, max(0.0, progress * duration_seconds))
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        frame = Image.open(io.BytesIO(result.stdout)).convert("RGBA")
        fitted = ImageOps.fit(frame, (width, height), method=Image.LANCZOS)
        enhanced = ImageEnhance.Contrast(fitted).enhance(1.05)
        enhanced = ImageEnhance.Color(enhanced).enhance(1.06)
        return enhanced.convert("RGB")
    except Exception as exc:
        logger.debug("Stock frame extract failed (%s): %s", video_path.name, exc)
        return None


def _create_bottom_gradient_overlay(width: int, height: int) -> Image.Image:
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    gradient_height = int(height * BOTTOM_GRADIENT_RATIO)
    gradient_top = height - gradient_height
    for row in range(gradient_top, height):
        blend = (row - gradient_top) / max(gradient_height - 1, 1)
        alpha = int(220 * blend**1.15)
        draw.line([(0, row), (width, row)], fill=(0, 0, 0, alpha))
    return overlay


def _draw_section_pill(
    draw: ImageDraw.ImageDraw,
    section_label: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    label = section_label.strip()[:42]
    if not label:
        return
    pill_font = font
    bbox = draw.textbbox((0, 0), label, font=pill_font)
    text_width = bbox[2] - bbox[0]
    box_x = 40
    box_y = 36
    box_width = text_width + 32
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_width, box_y + 40],
        radius=10,
        fill=(0, 0, 0, 170),
    )
    draw.text((box_x + 16, box_y + 8), label, fill=(255, 255, 255), font=pill_font)


def _draw_bottom_narration_text(
    draw: ImageDraw.ImageDraw,
    narration_words: list[str],
    visible_word_count: int,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    visible_words = narration_words[:visible_word_count]
    if not visible_words:
        return

    text = " ".join(visible_words)
    max_width = int(width * 0.88)
    wrapped_lines = textwrap.wrap(text, width=28)
    if not wrapped_lines:
        wrapped_lines = [text[:120]]

    line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + 12
    total_height = len(wrapped_lines) * line_height
    start_y = height - int(height * 0.08) - total_height

    for line_index, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x_position = (width - text_width) // 2
        y_position = start_y + (line_index * line_height)
        draw.text((x_position + 2, y_position + 2), line, fill=(0, 0, 0), font=font)
        draw.text((x_position, y_position), line, fill=(255, 255, 255), font=font)


def _load_subtitle_font(
    width: int,
    font_path: str | None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_size = 52 if width >= 1600 else 40
    if font_path:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            pass
    return ImageFont.load_default()
