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


@patch("futuredecoded.media.voice_engine.get_audio_duration", return_value=12.5)
@patch("futuredecoded.media.voice_engine._synthesise_voice_async", new_callable=AsyncMock)
def test_synthesise_voice_writes_srt(
    mock_synthesise: AsyncMock,
    mock_duration: MagicMock,
    tmp_path: Path,
):
    async def write_audio(_script_text: str, output_path: Path) -> None:
        output_path.write_bytes(b"fake-audio")

    mock_synthesise.side_effect = write_audio
    output_path = tmp_path / "voice_long.mp3"

    voice_path, duration = synthesise_voice("Hello world from FutureDecoded.", output_path)

    assert voice_path == output_path
    assert duration == 12.5
    assert output_path.with_suffix(".srt").exists()
    mock_synthesise.assert_awaited_once()


def test_synthesise_voice_raises_for_empty_script(tmp_path: Path):
    with pytest.raises(RuntimeError, match="empty after sanitization"):
        synthesise_voice("``` ```", tmp_path / "voice.mp3")
