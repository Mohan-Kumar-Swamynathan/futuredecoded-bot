"""Tests for watermark engine."""

from pathlib import Path

from futuredecoded.config.channel_profile import CHANNEL_NAME
from futuredecoded.media.watermark_engine import ensure_watermark_asset


def test_ensure_watermark_asset_generates_png(tmp_path: Path):
    watermark_path = ensure_watermark_asset(tmp_path)

    assert watermark_path.exists()
    assert watermark_path.suffix == ".png"
    assert watermark_path.stat().st_size > 0

    from PIL import Image

    image = Image.open(watermark_path)
    assert image.mode == "RGBA"
    assert CHANNEL_NAME  # asset generation uses channel branding constants
