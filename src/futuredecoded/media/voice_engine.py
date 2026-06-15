"""Voice generation — Edge TTS primary, Gemini TTS fallback, BGM mix."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

import edge_tts
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from futuredecoded.config.channel_profile import EDGE_TTS_PITCH, EDGE_TTS_RATE, EDGE_TTS_VOICE
from futuredecoded.config.settings import get_settings
from futuredecoded.media.audio_mixer import mix_narration_with_bgm
from futuredecoded.media.audio_utils import get_audio_duration
from futuredecoded.media.gemini_tts_engine import synthesise_voice_with_gemini

logger = logging.getLogger("futuredecoded.media.voice")

_STAGE_DIRECTION_PATTERN = re.compile(
    r"\[(?:pause|music|cut|b-roll|hook|cta)[^\]]*\]",
    flags=re.IGNORECASE,
)


def _strip_json_fences(text: str) -> str:
    return re.sub(r"```(?:json|text|markdown)?\s*|\s*```", "", text).strip()


def sanitize_script_for_tts(script_text: str) -> str:
    """Normalize LLM script output for TTS."""
    cleaned = _strip_json_fences(script_text or "")
    cleaned = _STAGE_DIRECTION_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"[*_#>`]", "", cleaned)
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _generate_srt(script_text: str, duration: float, words_per_segment: int = 12) -> str:
    words = script_text.split()
    segments = [
        " ".join(words[index : index + words_per_segment])
        for index in range(0, len(words), words_per_segment)
    ]
    if not segments:
        return ""
    seconds_per_segment = duration / len(segments)
    lines: list[str] = []
    for index, segment in enumerate(segments):
        start = index * seconds_per_segment
        end = (index + 1) * seconds_per_segment
        lines += [
            str(index + 1),
            f"{_format_timestamp(start)} --> {_format_timestamp(end)}",
            segment,
            "",
        ]
    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    millis = int((seconds - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((OSError, TimeoutError, RuntimeError)),
    reraise=True,
)
async def _synthesise_voice_async(script_text: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(
        script_text,
        voice=EDGE_TTS_VOICE,
        rate=EDGE_TTS_RATE,
        pitch=EDGE_TTS_PITCH,
        receive_timeout=120,
    )
    await communicate.save(str(output_path))
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Edge TTS produced an empty audio file")


def _synthesise_narration_track(cleaned_script: str, narration_path: Path) -> None:
    try:
        asyncio.run(_synthesise_voice_async(cleaned_script, narration_path))
        logger.info("Voice synthesised with Edge TTS")
        return
    except Exception as edge_error:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError(f"Edge TTS voice synthesis failed: {edge_error}") from edge_error
        logger.warning("Edge TTS failed, falling back to Gemini TTS: %s", str(edge_error)[:200])
        synthesise_voice_with_gemini(cleaned_script, narration_path)
        logger.info("Voice synthesised with Gemini TTS fallback")


def synthesise_voice(
    script_text: str,
    output_path: Path,
    format_type: str = "long",
    mix_bgm: bool = True,
) -> tuple[Path, float]:
    cleaned_script = sanitize_script_for_tts(script_text)
    if not cleaned_script:
        raise RuntimeError("Script text is empty after sanitization — cannot synthesise voice")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Synthesising voice (%d chars, format=%s) -> %s",
        len(cleaned_script),
        format_type,
        output_path.name,
    )

    narration_path = output_path.with_name(f"{output_path.stem}_narration{output_path.suffix}")
    _synthesise_narration_track(cleaned_script, narration_path)

    if mix_bgm:
        try:
            mix_narration_with_bgm(narration_path, output_path, format_type=format_type)
        except Exception as bgm_error:
            logger.warning("BGM mix failed, using narration only: %s", bgm_error)
            shutil.copy(narration_path, output_path)
    else:
        shutil.copy(narration_path, output_path)

    final_audio_path = output_path

    duration = get_audio_duration(final_audio_path)
    if duration <= 0:
        raise RuntimeError(f"Generated audio has invalid duration: {final_audio_path}")

    srt_path = output_path.with_suffix(".srt")
    srt_path.write_text(_generate_srt(cleaned_script, duration), encoding="utf-8")
    logger.info("Voice ready: %s (%.1fs)", final_audio_path.name, duration)
    return final_audio_path, duration
