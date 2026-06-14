"""Thumbnail engine — hero image, high contrast, cross-platform fonts."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("futuredecoded.media.thumbnail")

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def _load_title_font(size: int = 72):
    from PIL import ImageFont

    for font_path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _load_brand_font(size: int = 36):
    from PIL import ImageFont

    for font_path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _extract_video_frame(video_path: Path, frame_path: Path, frame_time: float) -> bool:
    if not video_path.exists():
        return False
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(frame_time),
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and frame_path.exists()


def _load_base_image(
    hero_image: Path | None,
    video_path: Path,
    frame_path: Path,
    frame_time: float,
):
    from PIL import Image, ImageOps

    if hero_image and hero_image.exists():
        return ImageOps.fit(Image.open(hero_image).convert("RGB"), (1280, 720), method=ImageOps.LANCZOS)

    if _extract_video_frame(video_path, frame_path, frame_time):
        return ImageOps.fit(Image.open(frame_path).convert("RGB"), (1280, 720), method=ImageOps.LANCZOS)

    return Image.new("RGB", (1280, 720), (15, 25, 45))


def _draw_text_with_stroke(draw, position, text, font, fill, stroke_fill, stroke_width=3):
    x_pos, y_pos = position
    for offset_x in range(-stroke_width, stroke_width + 1):
        for offset_y in range(-stroke_width, stroke_width + 1):
            if offset_x == 0 and offset_y == 0:
                continue
            draw.text((x_pos + offset_x, y_pos + offset_y), text, font=font, fill=stroke_fill)
    draw.text((x_pos, y_pos), text, font=font, fill=fill)


def generate_thumbnail(
    video_path: Path,
    thumbnail_text: str,
    output_path: Path,
    frame_time: float = 3.0,
    hero_image: Path | None = None,
) -> Path | None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow not installed")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path = output_path.parent / f"{output_path.stem}_frame.jpg"
    base_image = _load_base_image(hero_image, video_path, frame_path, frame_time)

    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([(0, 420), (1280, 720)], fill=(0, 0, 0, 190))
    overlay_draw.rectangle([(0, 420), (18, 720)], fill=(255, 196, 0, 255))
    composed = Image.alpha_composite(base_image.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(composed)
    title_font = _load_title_font(72)
    brand_font = _load_brand_font(34)
    headline = " ".join(thumbnail_text.split()[:4]).upper()

    _draw_text_with_stroke(
        draw,
        (48, 470),
        headline,
        title_font,
        fill=(255, 220, 50),
        stroke_fill=(0, 0, 0),
        stroke_width=3,
    )
    draw.text((48, 620), "FutureDecoded", fill=(220, 220, 220), font=brand_font)
    draw.text((48, 665), "Making Sense of Tomorrow", fill=(170, 170, 170), font=brand_font)

    composed.save(output_path, quality=95)
    logger.info("Thumbnail saved: %s", output_path.name)
    return output_path
