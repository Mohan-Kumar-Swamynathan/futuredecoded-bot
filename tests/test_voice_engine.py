"""Tests for voice engine script sanitization."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from futuredecoded.media.voice_engine import sanitize_script_for_tts, synthesise_voice


def test_sanitize_script_for_tts_removes_markdown_and_stage_directions():
    raw = """```json
**Hook:** Amazon just made a move.
[PAUSE]
## Why it matters
This is *important*.
```"""
    cleaned = sanitize_script_for_tts(raw)
    assert "Hook:" in cleaned
    assert "**" not in cleaned
    assert "[PAUSE]" not in cleaned
    assert "```" not in cleaned


def test_sanitize_script_for_tts_returns_empty_for_blank_input():
    assert sanitize_script_for_tts("   ") == ""


@patch("futuredecoded.media.voice_engine.mix_narration_with_bgm")
@patch("futuredecoded.media.voice_engine.get_audio_duration", return_value=12.5)
@patch("futuredecoded.media.voice_engine._synthesise_voice_async", new_callable=AsyncMock)
def test_synthesise_voice_writes_srt(
    mock_synthesise: AsyncMock,
    mock_duration: MagicMock,
    mock_mix_bgm: MagicMock,
    tmp_path: Path,
):
    async def write_audio(_script_text: str, output_path: Path):
        output_path.write_bytes(b"fake-audio")
        return []

    mock_synthesise.side_effect = write_audio

    def copy_mixed(narration_path: Path, output_path: Path, format_type: str = "long") -> Path:
        output_path.write_bytes(b"fake-audio")
        return output_path

    mock_mix_bgm.side_effect = copy_mixed
    output_path = tmp_path / "voice_long.mp3"

    voice_path, duration = synthesise_voice("Hello world from FutureDecoded.", output_path)

    assert voice_path == output_path
    assert duration == 12.5
    assert output_path.with_suffix(".ass").exists()
    mock_synthesise.assert_awaited_once()
    mock_mix_bgm.assert_called_once()


def test_synthesise_voice_raises_for_empty_script(tmp_path: Path):
    with pytest.raises(RuntimeError, match="empty after sanitization"):
        synthesise_voice("``` ```", tmp_path / "voice.mp3")


@patch("futuredecoded.media.voice_engine.mix_narration_with_bgm")
@patch("futuredecoded.media.voice_engine.get_audio_duration", return_value=8.0)
@patch("futuredecoded.media.voice_engine.synthesise_voice_with_gemini")
@patch("futuredecoded.media.voice_engine._synthesise_voice_async", new_callable=AsyncMock)
@patch("futuredecoded.media.voice_engine.get_settings")
def test_synthesise_voice_falls_back_to_gemini_when_edge_fails(
    mock_settings,
    mock_edge: AsyncMock,
    mock_gemini,
    _mock_duration,
    mock_mix_bgm,
    tmp_path: Path,
):
    settings = MagicMock()
    settings.gemini_api_key = "gemini-key"
    mock_settings.return_value = settings
    mock_edge.side_effect = RuntimeError("edge failed")

    def write_gemini(script_text: str, output_path: Path) -> None:
        output_path.write_bytes(b"gemini-audio")

    mock_gemini.side_effect = write_gemini

    def copy_mixed(narration_path: Path, output_path: Path, format_type: str = "long") -> Path:
        output_path.write_bytes(b"gemini-audio")
        return output_path

    mock_mix_bgm.side_effect = copy_mixed
    output_path = tmp_path / "voice.mp3"

    voice_path, duration = synthesise_voice("Gemini fallback narration.", output_path)

    assert voice_path == output_path
    assert duration == 8.0
    mock_gemini.assert_called_once()
