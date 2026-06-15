"""Tests for Gemini TTS fallback."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from futuredecoded.media.gemini_tts_engine import _split_script_for_tts, synthesise_voice_with_gemini


def test_split_script_for_tts_chunks_long_paragraphs():
    long_paragraph = "Sentence one. " * 200
    chunks = _split_script_for_tts(long_paragraph, max_chars=500)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 500 for chunk in chunks)


@patch("futuredecoded.media.gemini_tts_engine._convert_wav_to_mp3")
@patch("futuredecoded.media.gemini_tts_engine._synthesise_chunk_with_gemini")
@patch("futuredecoded.media.gemini_tts_engine.get_settings")
def test_synthesise_voice_with_gemini_writes_mp3(
    mock_settings,
    mock_synthesise_chunk,
    mock_convert,
    tmp_path: Path,
):
    settings = MagicMock()
    settings.gemini_api_key = "test-key"
    mock_settings.return_value = settings

    def write_wav(chunk_text: str, output_wav_path: Path, api_key: str) -> None:
        output_wav_path.write_bytes(b"wav")

    mock_synthesise_chunk.side_effect = write_wav

    def convert_wav(wav_path: Path, mp3_path: Path) -> None:
        mp3_path.write_bytes(b"mp3")

    mock_convert.side_effect = convert_wav

    output_path = tmp_path / "voice.mp3"
    synthesise_voice_with_gemini("OpenAI just launched a new agent.", output_path)
    assert output_path.exists()


@patch("futuredecoded.media.gemini_tts_engine.get_settings")
def test_synthesise_voice_with_gemini_requires_api_key(mock_settings, tmp_path: Path):
    settings = MagicMock()
    settings.gemini_api_key = ""
    mock_settings.return_value = settings

    with pytest.raises(RuntimeError, match="Gemini API key"):
        synthesise_voice_with_gemini("Hello", tmp_path / "voice.mp3")
