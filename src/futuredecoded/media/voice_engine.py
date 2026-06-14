"""Edge TTS voice generation with SRT subtitles."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from pathlib import Path

import edge_tts
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from futuredecoded.config.channel_profile import EDGE_TTS_PITCH, EDGE_TTS_RATE, EDGE_TTS_VOICE

logger = logging.getLogger("futuredecoded.media.voice")

_STAGE_DIRECTION_PATTERN = re.compile(
    r"\[(?:pause|music|cut|b-roll|hook|cta)[^\]]*\]",
    flags=re.IGNORECASE,
)


def _strip_json_fences(text: str) -> str:
    return re.sub(r"```(?:json|text|markdown)?\s*|\s*```", "", text).strip()


def sanitize_script_for_tts(script_text: str) -> str:
    """Normalize LLM script output for Edge TTS."""
    cleaned = _strip_json_fences(script_text or "")
    cleaned = _STAGE_DIRECTION_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"[*_#>`]", "", cleaned)
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


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


def synthesise_voice(script_text: str, output_path: Path) -> tuple[Path, float]:
    cleaned_script = sanitize_script_for_tts(script_text)
    if not cleaned_script:
        raise RuntimeError("Script text is empty after sanitization — cannot synthesise voice")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Synthesising voice (%d chars) -> %s",
        len(cleaned_script),
        output_path.name,
    )

    try:
        asyncio.run(_synthesise_voice_async(cleaned_script, output_path))
    except Exception as exc:
        raise RuntimeError(f"Edge TTS voice synthesis failed: {exc}") from exc

    duration = get_audio_duration(output_path)
    if duration <= 0:
        raise RuntimeError(f"Generated audio has invalid duration: {output_path}")

    srt_path = output_path.with_suffix(".srt")
    srt_path.write_text(_generate_srt(cleaned_script, duration), encoding="utf-8")
    logger.info("Voice synthesised: %s (%.1fs)", output_path.name, duration)
    return output_path, duration
