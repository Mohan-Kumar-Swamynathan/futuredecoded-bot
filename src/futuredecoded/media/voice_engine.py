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
from futuredecoded.llm.provider_client import get_llm_client
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


SSML_REWRITE_PROMPT = """You are a world-class speech writer, linguist, and prosody engineer specializing in Microsoft Azure Neural Text-to-Speech.
Your task is to transform the provided text into highly natural, human-like speech optimized for Microsoft Edge TTS.

Primary Goal: Make the audio sound as close as possible to a real human speaker in English.

Requirements:
- Preserve meaning exactly; do not add or remove information.
- Rewrite written text into natural spoken language.
- Improve conversational flow and rhythm.
- Break long sentences into shorter, natural speech units.
- Add realistic pauses where humans naturally pause.
- Use punctuation strategically to improve prosody and intonation.
- Avoid robotic, repetitive, overly formal, or book-like phrasing.
- Make the speech sound warm, engaging, confident, and natural.
- Optimize for listeners rather than readers.
- Make narration sound like a professional tech presenter or podcast host.

Rules:
- Return ONLY the rewritten plain text. No SSML tags, no XML, no markdown.
- Do not add or remove information.
- Natural contractions are fine: "it is" → "it's", "we are" → "we're"
- Short punchy sentences for key facts. Longer flowing sentences for context.
- Numbers should be spoken naturally: "1000000" → "one million", "3.5x" → "three and a half times faster"

Input Text:
{text}"""


def rewrite_for_naturalness(script_text: str) -> str:
    """Use LLM to rewrite script into natural spoken form before TTS."""
    try:
        llm = get_llm_client()
        prompt = SSML_REWRITE_PROMPT.format(text=script_text[:4000])
        rewritten = llm.call(prompt, max_tokens=5000)
        if rewritten and len(rewritten.strip()) > 100:
            logger.info("Script rewritten for naturalness: %d → %d chars",
                       len(script_text), len(rewritten))
            return rewritten.strip()
    except Exception as e:
        logger.warning("LLM rewrite failed (%s) — using original script", e)
    return script_text


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


def _word_timing_from_boundary(chunk: dict) -> WordTiming:
    start_seconds = chunk["offset"] / 10_000_000
    end_seconds = (chunk["offset"] + chunk["duration"]) / 10_000_000
    return WordTiming(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        text=str(chunk["text"]),
    )


def _build_srt_from_word_timings(word_timings: list[WordTiming], words_per_cue: int = 8) -> str:
    if not word_timings:
        return ""

    lines: list[str] = []
    cue_index = 1
    for chunk_start in range(0, len(word_timings), words_per_cue):
        chunk = word_timings[chunk_start : chunk_start + words_per_cue]
        if not chunk:
            continue
        start_seconds = chunk[0].start_seconds
        end_seconds = chunk[-1].end_seconds
        text = " ".join(word.text for word in chunk)
        lines += [
            str(cue_index),
            f"{_format_srt_timestamp(start_seconds)} --> {_format_srt_timestamp(end_seconds)}",
            text,
            "",
        ]
        cue_index += 1
    return "\n".join(lines)


def _format_srt_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    millis = int(round((seconds - total_seconds) * 1000))
    if millis >= 1000:
        total_seconds += 1
        millis = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _estimate_minimum_narration_seconds(script_text: str) -> float:
    word_count = len(script_text.split())
    if word_count == 0:
        return 3.0
    # ~150 wpm narration => 2.5 words/sec; allow generous floor for short scripts.
    return max(3.0, word_count / 2.5)


def _is_usable_narration_file(narration_path: Path, script_text: str) -> bool:
    if not narration_path.exists() or narration_path.stat().st_size < 1024:
        return False
    duration_seconds = get_audio_duration(narration_path)
    minimum_seconds = _estimate_minimum_narration_seconds(script_text)
    return duration_seconds >= max(3.0, minimum_seconds * 0.35)


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
        boundary="WordBoundary",
        receive_timeout=120,
    )
    word_timings: list[WordTiming] = []

    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append(_word_timing_from_boundary(chunk))

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Edge TTS produced an empty audio file")

    if not _is_usable_narration_file(output_path, script_text):
        duration_seconds = get_audio_duration(output_path)
        raise RuntimeError(
            f"Edge TTS produced unusable narration ({duration_seconds:.1f}s for {len(script_text.split())} words)"
        )

    srt_path = output_path.with_suffix(".srt")
    srt_content = _build_srt_from_word_timings(word_timings)
    if srt_content.strip():
        srt_path.write_text(srt_content, encoding="utf-8")
    return word_timings


def _synthesise_narration_track(cleaned_script: str, narration_path: Path) -> list[WordTiming]:
    edge_error: Exception | None = None
    try:
        word_timings = asyncio.run(_synthesise_voice_async(cleaned_script, narration_path))
        logger.info("Voice synthesised with Edge TTS (%d word timings)", len(word_timings))
        return word_timings
    except Exception as exc:
        edge_error = exc
        if _is_usable_narration_file(narration_path, cleaned_script):
            duration_seconds = get_audio_duration(narration_path)
            logger.warning(
                "Edge TTS post-processing failed but narration audio is usable (%.1fs) — keeping Edge output: %s",
                duration_seconds,
                str(edge_error)[:200],
            )
            return []

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(f"Edge TTS voice synthesis failed: {edge_error}") from edge_error
    logger.warning("Edge TTS failed, falling back to Gemini TTS: %s", str(edge_error)[:200])
    synthesise_voice_with_gemini(cleaned_script, narration_path)
    if not _is_usable_narration_file(narration_path, cleaned_script):
        duration_seconds = get_audio_duration(narration_path)
        raise RuntimeError(
            f"Gemini TTS produced unusable narration ({duration_seconds:.1f}s for {len(cleaned_script.split())} words)"
        ) from edge_error
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

    if not word_timings:
        save_word_timings([], output_path.with_suffix(".word_timings.json"))
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

    # Rewrite for natural spoken cadence before TTS
    natural_script = rewrite_for_naturalness(cleaned_script)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Synthesising voice (%d chars → %d chars natural, format=%s) -> %s",
        len(cleaned_script),
        len(natural_script),
        format_type,
        output_path.name,
    )

    narration_path = output_path.with_name(f"{output_path.stem}_narration{output_path.suffix}")
    word_timings = _synthesise_narration_track(natural_script, narration_path)

    narration_srt = narration_path.with_suffix(".srt")
    output_srt = output_path.with_suffix(".srt")
    if narration_srt.exists() and not output_srt.exists():
        shutil.copy(narration_srt, output_srt)

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
    minimum_seconds = _estimate_minimum_narration_seconds(cleaned_script)
    if duration <= 0:
        raise RuntimeError(f"Generated audio has invalid duration: {final_audio_path}")
    if duration < max(3.0, minimum_seconds * 0.35):
        raise RuntimeError(
            f"Generated audio too short ({duration:.1f}s, expected at least {minimum_seconds:.1f}s): {final_audio_path}"
        )

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
