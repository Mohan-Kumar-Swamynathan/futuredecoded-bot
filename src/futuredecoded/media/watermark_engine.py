"""Channel watermark asset generation and overlay helpers."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from futuredecoded.config.channel_profile import (
    CHANNEL_NAME,
    CHANNEL_TAGLINE,
    WATERMARK_FILENAME,
    WATERMARK_MARGIN_PX,
    WATERMARK_OPACITY,
)
from futuredecoded.config.settings import get_settings
from futuredecoded.media.font_resolver import escape_ffmpeg_path
from futuredecoded.media.video_export_settings import (
    ffmpeg_crf,
    ffmpeg_preset,
    finalize_render_timeout_seconds,
)

logger = logging.getLogger("futuredecoded.media.watermark")

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

SUBTITLE_STYLE = (
    "FontName=DejaVu Sans Bold,FontSize=42,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,Outline=3,Shadow=1,MarginV=90,Alignment=2,Bold=1"
)


def ensure_watermark_asset(assets_dir: Path | None = None) -> Path:
    settings = get_settings()
    resolved_assets_dir = assets_dir or settings.assets_dir
    resolved_assets_dir.mkdir(parents=True, exist_ok=True)
    watermark_path = resolved_assets_dir / WATERMARK_FILENAME

    if watermark_path.exists() and watermark_path.stat().st_size > 0:
        return watermark_path

    _generate_watermark_png(watermark_path)
    return watermark_path


def _load_font(size: int):
    from PIL import ImageFont

    for font_path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _generate_watermark_png(output_path: Path) -> None:
    from PIL import Image, ImageDraw

    width, height = 420, 110
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    alpha = int(255 * WATERMARK_OPACITY)
    draw.rounded_rectangle(
        [(0, 0), (width - 1, height - 1)],
        radius=14,
        fill=(0, 0, 0, int(alpha * 0.55)),
    )
    draw.rectangle([(0, 12), (6, height - 12)], fill=(255, 196, 0, alpha))

    title_font = _load_font(34)
    tagline_font = _load_font(18)
    draw.text((20, 18), CHANNEL_NAME, fill=(255, 220, 80, alpha), font=title_font)
    draw.text((20, 62), CHANNEL_TAGLINE, fill=(220, 220, 220, int(alpha * 0.9)), font=tagline_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    logger.info("Generated watermark asset: %s", output_path.name)


def apply_watermark_to_video(
    video_path: Path,
    output_path: Path,
    width: int,
    height: int,
    caption_path: Path | None = None,
    srt_path: Path | None = None,
) -> bool:
    resolved_caption_path = caption_path or srt_path
    watermark_path = ensure_watermark_asset()
    if not watermark_path.exists():
        logger.warning("Watermark asset missing — skipping overlay")
        return False

    overlay_x = f"main_w-overlay_w-{WATERMARK_MARGIN_PX}"
    overlay_y = f"main_h-overlay_h-{WATERMARK_MARGIN_PX}"
    if height > width:
        overlay_y = str(WATERMARK_MARGIN_PX)

    caption_for_filter = _prepare_caption_path(resolved_caption_path)
    subtitle_stage = "[0:v]"
    if caption_for_filter and caption_for_filter.exists():
        escaped_caption = escape_ffmpeg_path(caption_for_filter)
        subtitle_stage = (
            f"[0:v]subtitles='{escaped_caption}':force_style='{SUBTITLE_STYLE}'[subbed];[subbed]"
        )

    video_filter = f"{subtitle_stage}[1:v]overlay={overlay_x}:{overlay_y}:format=auto:shortest=1[vout]"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(watermark_path),
        "-filter_complex",
        video_filter,
        "-map",
        "[vout]",
        "-map",
        "0:a?",
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
    result = subprocess.run(command, capture_output=True, text=True, timeout=finalize_render_timeout_seconds(), check=False)
    if result.returncode == 0:
        logger.info("Applied channel watermark: %s", output_path.name)
        return True

    logger.warning("Watermark+caption overlay failed, retrying watermark only: %s", result.stderr[-250:])
    return _apply_watermark_only(video_path, output_path, watermark_path, overlay_x, overlay_y)


def _prepare_caption_path(caption_path: Path | None) -> Path | None:
    if caption_path is None or not caption_path.exists():
        return None
    if caption_path.stat().st_size == 0:
        return None
    return caption_path


def _apply_watermark_only(
    video_path: Path,
    output_path: Path,
    watermark_path: Path,
    overlay_x: str,
    overlay_y: str,
) -> bool:
    video_filter = f"[0:v][1:v]overlay={overlay_x}:{overlay_y}:format=auto:shortest=1[vout]"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(watermark_path),
        "-filter_complex",
        video_filter,
        "-map",
        "[vout]",
        "-map",
        "0:a?",
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
    result = subprocess.run(command, capture_output=True, text=True, timeout=finalize_render_timeout_seconds(), check=False)
    if result.returncode != 0:
        logger.warning("Watermark-only overlay failed: %s", result.stderr[-250:])
        return False
    logger.info("Applied watermark without captions: %s", output_path.name)
    return True
