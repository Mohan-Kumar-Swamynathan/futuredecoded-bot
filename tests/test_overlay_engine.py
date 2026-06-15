"""Tests for overlay engine."""

from unittest.mock import patch

from futuredecoded.media.overlay_engine import build_overlay_drawtext_filter, escape_drawtext_text


def test_escape_drawtext_text_sanitizes_special_characters():
    assert escape_drawtext_text("GPT-5: launch") == "GPT-5  LAUNCH"
    assert "," not in escape_drawtext_text("Hello, world")


@patch("futuredecoded.media.overlay_engine.is_drawtext_available", return_value=True)
def test_build_overlay_drawtext_filter_returns_ffmpeg_filter(_mock_drawtext):
    overlay = build_overlay_drawtext_filter("OPENAI LAUNCH", width=1920, height=1080, is_hook_scene=True)
    assert "drawtext=text=" in overlay
    assert "fontsize=64" in overlay
