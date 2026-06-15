"""Gemini TTS fallback — used when Edge TTS fails."""

from __future__ import annotations

import base64
import logging
import subprocess
import wave
from pathlib import Path

from futuredecoded.config.channel_profile import (
    GEMINI_TTS_MAX_CHARS_PER_CHUNK,
    GEMINI_TTS_MODELS,
    GEMINI_TTS_VOICE,
)
from futuredecoded.config.settings import get_settings

logger = logging.getLogger("futuredecoded.media.gemini_tts")


def synthesise_voice_with_gemini(script_text: str, output_path: Path) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API key is not configured for TTS fallback")

    chunks = _split_script_for_tts(script_text, GEMINI_TTS_MAX_CHARS_PER_CHUNK)
    if not chunks:
        raise RuntimeError("Script text is empty — cannot synthesise with Gemini TTS")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_wav_paths: list[Path] = []

    for index, chunk in enumerate(chunks):
        chunk_wav = output_path.parent / f"{output_path.stem}_gemini_{index:02d}.wav"
        _synthesise_chunk_with_gemini(chunk, chunk_wav, settings.gemini_api_key)
        chunk_wav_paths.append(chunk_wav)

    merged_wav = output_path.with_suffix(".wav")
    if len(chunk_wav_paths) == 1:
        merged_wav = chunk_wav_paths[0]
    else:
        _concatenate_wav_files(chunk_wav_paths, merged_wav)

    _convert_wav_to_mp3(merged_wav, output_path)
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Gemini TTS produced an empty audio file")


def _split_script_for_tts(script_text: str, max_chars: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in script_text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        cleaned = script_text.strip()
        return [cleaned] if cleaned else []

    chunks: list[str] = []
    current_chunk = ""
    for paragraph in paragraphs:
        candidate = f"{current_chunk}\n\n{paragraph}".strip() if current_chunk else paragraph
        if len(candidate) <= max_chars:
            current_chunk = candidate
            continue
        if current_chunk:
            chunks.append(current_chunk)
        if len(paragraph) <= max_chars:
            current_chunk = paragraph
        else:
            sentences = _split_sentences(paragraph)
            sentence_chunk = ""
            for sentence in sentences:
                candidate_sentence = f"{sentence_chunk} {sentence}".strip()
                if len(candidate_sentence) <= max_chars:
                    sentence_chunk = candidate_sentence
                else:
                    if sentence_chunk:
                        chunks.append(sentence_chunk)
                    sentence_chunk = sentence
            current_chunk = sentence_chunk

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _split_sentences(paragraph: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    return [part.strip() for part in parts if part.strip()]


def _synthesise_chunk_with_gemini(chunk_text: str, output_wav_path: Path, api_key: str) -> None:
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    last_error: Exception | None = None

    for model_name in GEMINI_TTS_MODELS:
        try:
            logger.info("Gemini TTS attempt: model=%s chars=%d", model_name, len(chunk_text))
            response = client.models.generate_content(
                model=model_name,
                contents=f"Read this tech news narration clearly and professionally:\n\n{chunk_text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=GEMINI_TTS_VOICE,
                            )
                        )
                    ),
                ),
            )
            pcm_data = _extract_pcm_audio(response)
            _write_pcm_as_wav(pcm_data, output_wav_path)
            logger.info("Gemini TTS succeeded: model=%s", model_name)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini TTS model %s failed: %s", model_name, str(exc)[:200])

    raise RuntimeError(f"All Gemini TTS models failed: {last_error}")


def _extract_pcm_audio(response) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise RuntimeError("Gemini TTS returned no candidates")

    content = candidates[0].content
    parts = getattr(content, "parts", None) or []
    if not parts:
        raise RuntimeError("Gemini TTS returned no audio parts")

    inline_data = parts[0].inline_data
    raw_data = inline_data.data
    if isinstance(raw_data, str):
        return base64.b64decode(raw_data)
    if isinstance(raw_data, bytes):
        try:
            return base64.b64decode(raw_data)
        except Exception:
            return raw_data
    raise RuntimeError("Gemini TTS returned unsupported audio payload")


def _write_pcm_as_wav(pcm_data: bytes, output_wav_path: Path) -> None:
    minimum_bytes = 24000 * 2  # at least ~1 second of mono 16-bit PCM at 24 kHz
    if len(pcm_data) < minimum_bytes:
        raise RuntimeError(f"Gemini TTS returned truncated PCM audio ({len(pcm_data)} bytes)")

    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(pcm_data)


def _concatenate_wav_files(wav_paths: list[Path], output_wav_path: Path) -> None:
    concat_list_path = output_wav_path.parent / "gemini_tts_concat.txt"
    concat_list_path.write_text(
        "\n".join(f"file '{wav_path}'" for wav_path in wav_paths),
        encoding="utf-8",
    )
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c",
        "copy",
        str(output_wav_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Gemini TTS WAV concat failed: {result.stderr[-300:]}")


def _convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-qscale:a",
        "2",
        str(mp3_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Gemini TTS MP3 conversion failed: {result.stderr[-300:]}")
