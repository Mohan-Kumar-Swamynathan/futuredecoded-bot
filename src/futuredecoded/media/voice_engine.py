"""Voice generation — Edge TTS primary, Gemini TTS fallback, BGM mix, word captions."""

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
from futuredecoded.media.caption_engine import WordTiming, build_ass_from_srt, build_ass_subtitles, save_word_timings
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


def _generate_srt(script_text: str, duration: float, words_per_segment: int = 8) -> str:
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
async def _synthesise_voice_async(script_text: str, output_path: Path) -> list[WordTiming]:
    communicate = edge_tts.Communicate(
        script_text,
        voice=EDGE_TTS_VOICE,
        rate=EDGE_TTS_RATE,
        pitch=EDGE_TTS_PITCH,
        receive_timeout=120,
    )
    submaker = edge_tts.SubMaker()
    word_timings: list[WordTiming] = []

    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
                start_seconds = chunk["offset"] / 10_000_000
                end_seconds = (chunk["offset"] + chunk["duration"]) / 10_000_000
                word_timings.append(
                    WordTiming(
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        text=str(chunk["text"]),
                    )
                )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Edge TTS produced an empty audio file")

    srt_path = output_path.with_suffix(".srt")
    srt_path.write_text(submaker.generate_subs(), encoding="utf-8")
    return word_timings


def _synthesise_narration_track(cleaned_script: str, narration_path: Path) -> list[WordTiming]:
    try:
        word_timings = asyncio.run(_synthesise_voice_async(cleaned_script, narration_path))
        logger.info("Voice synthesised with Edge TTS (%d word timings)", len(word_timings))
        return word_timings
    except Exception as edge_error:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError(f"Edge TTS voice synthesis failed: {edge_error}") from edge_error
        logger.warning("Edge TTS failed, falling back to Gemini TTS: %s", str(edge_error)[:200])
        synthesise_voice_with_gemini(cleaned_script, narration_path)
        logger.info("Voice synthesised with Gemini TTS fallback")
        return []


def _write_caption_files(
    cleaned_script: str,
    output_path: Path,
    duration: float,
    word_timings: list[WordTiming],
    play_res_x: int,
    play_res_y: int,
) -> Path:
    srt_path = output_path.with_suffix(".srt")
    ass_path = output_path.with_suffix(".ass")

    if word_timings:
        save_word_timings(word_timings, output_path.with_suffix(".word_timings.json"))
        build_ass_subtitles(word_timings, ass_path, play_res_x=play_res_x, play_res_y=play_res_y)
        if not srt_path.exists():
            srt_path.write_text(_generate_srt(cleaned_script, duration), encoding="utf-8")
        return ass_path

    if not srt_path.exists():
        srt_path.write_text(_generate_srt(cleaned_script, duration), encoding="utf-8")
    return build_ass_from_srt(srt_path, ass_path, play_res_x=play_res_x, play_res_y=play_res_y)


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
    word_timings = _synthesise_narration_track(cleaned_script, narration_path)

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

    play_res_x = 1080 if format_type == "short" else 1920
    play_res_y = 1920 if format_type == "short" else 1080
    caption_path = _write_caption_files(
        cleaned_script,
        output_path,
        duration,
        word_timings,
        play_res_x=play_res_x,
        play_res_y=play_res_y,
    )
    logger.info("Voice ready: %s (%.1fs, captions=%s)", final_audio_path.name, duration, caption_path.name)
    return final_audio_path, duration
