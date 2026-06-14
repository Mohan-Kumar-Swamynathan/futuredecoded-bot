"""Thumbnail engine — high contrast, max 4 words."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("futuredecoded.media.thumbnail")


def generate_thumbnail(
    video_path: Path,
    thumbnail_text: str,
    output_path: Path,
    frame_time: float = 3.0,
) -> Path | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Pillow not installed")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path = output_path.parent / f"{output_path.stem}_frame.jpg"

    import subprocess
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(frame_time), "-i", str(video_path),
            "-vframes", "1", "-q:v", "2", str(frame_path),
        ],
        capture_output=True, timeout=30,
    )

    if not frame_path.exists():
        img = __import__("PIL.Image", fromlist=["Image"]).Image.new("RGB", (1280, 720), (15, 25, 45))
    else:
        img = Image.open(frame_path).convert("RGB").resize((1280, 720))

    draw = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([(0, 500), (1280, 720)], fill=(0, 0, 0, 180))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    words = " ".join(thumbnail_text.split()[:4]).upper()
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 72)
    except OSError:
        font = ImageFont.load_default()

    draw.text((60, 540), words, fill=(255, 220, 50), font=font)
    draw.text((60, 620), "FutureDecoded", fill=(200, 200, 200), font=font)
    img.save(output_path, quality=95)

    prompt_path = output_path.with_suffix(".prompt.txt")
    prompt_path.write_text(
        f"High contrast tech thumbnail. Text: {words}. Dark blue background. AI news style.",
        encoding="utf-8",
    )
    logger.info("Thumbnail saved: %s", output_path.name)
    return output_path
