"""Tests for thumbnail engine Pillow compatibility."""

from pathlib import Path
from unittest.mock import patch

from futuredecoded.media.thumbnail_engine import _load_base_image, _resample_lanczos, generate_thumbnail


def _save_test_jpeg(path: Path) -> None:
    from PIL import Image

    Image.new("RGB", (1600, 900), (30, 40, 80)).save(path, format="JPEG")


def test_resample_lanczos_is_available():
    resample = _resample_lanczos()
    assert resample is not None


def test_load_base_image_uses_hero_image(tmp_path: Path):
    hero_path = tmp_path / "hero.jpg"
    _save_test_jpeg(hero_path)

    image = _load_base_image(hero_path, tmp_path / "missing.mp4", tmp_path / "frame.jpg", 1.0)
    assert image.size == (1280, 720)


def test_generate_thumbnail_creates_file(tmp_path: Path):
    hero_path = tmp_path / "hero.jpg"
    _save_test_jpeg(hero_path)
    output_path = tmp_path / "thumbnail.png"

    with patch("futuredecoded.media.thumbnail_engine._extract_video_frame", return_value=False):
        result = generate_thumbnail(
            video_path=tmp_path / "video.mp4",
            thumbnail_text="Amazon CEO AI Crackdown",
            output_path=output_path,
            hero_image=hero_path,
        )

    assert result == output_path
    assert output_path.exists()
