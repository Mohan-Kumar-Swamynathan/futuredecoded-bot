"""Caption engine — word-timed ASS subtitles (zero-cost, ffmpeg-compatible)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WordTiming:
    start_seconds: float
    end_seconds: float
    text: str


def save_word_timings(word_timings: list[WordTiming], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"start_seconds": item.start_seconds, "end_seconds": item.end_seconds, "text": item.text}
        for item in word_timings
    ]
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_ass_subtitles(
    word_timings: list[WordTiming],
    output_path: Path,
    play_res_x: int = 1920,
    play_res_y: int = 1080,
    words_per_line: int = 6,
) -> Path:
    if not word_timings:
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = _group_words_into_chunks(word_timings, words_per_line=words_per_line)
    dialogue_lines = [_build_karaoke_dialogue(chunk) for chunk in chunks if chunk]

    ass_header = _build_ass_header(play_res_x=play_res_x, play_res_y=play_res_y)
    output_path.write_text(ass_header + "\n".join(dialogue_lines) + "\n", encoding="utf-8")
    return output_path


def slice_word_timings_for_scene(
    word_timings: list[WordTiming],
    scene_start_seconds: float,
    scene_duration_seconds: float,
) -> list[WordTiming]:
    """Return word timings shifted to scene-local zero."""
    if scene_duration_seconds <= 0:
        return []

    scene_end_seconds = scene_start_seconds + scene_duration_seconds
    sliced: list[WordTiming] = []
    for timing in word_timings:
        if timing.end_seconds <= scene_start_seconds:
            continue
        if timing.start_seconds >= scene_end_seconds:
            break
        sliced.append(
            WordTiming(
                start_seconds=max(0.0, timing.start_seconds - scene_start_seconds),
                end_seconds=min(
                    scene_duration_seconds,
                    timing.end_seconds - scene_start_seconds,
                ),
                text=timing.text,
            )
        )
    return sliced


def build_scene_ass_subtitles(
    word_timings: list[WordTiming],
    scene_start_seconds: float,
    scene_duration_seconds: float,
    output_path: Path,
    play_res_x: int = 1920,
    play_res_y: int = 1080,
    words_per_line: int = 6,
) -> Path:
    """Build ASS subtitles for one scene window from full-narration word timings."""
    scene_timings = slice_word_timings_for_scene(
        word_timings,
        scene_start_seconds,
        scene_duration_seconds,
    )
    return build_ass_subtitles(
        scene_timings,
        output_path,
        play_res_x=play_res_x,
        play_res_y=play_res_y,
        words_per_line=words_per_line,
    )


def build_ass_from_srt(srt_path: Path, ass_path: Path, play_res_x: int = 1920, play_res_y: int = 1080) -> Path:
    if not srt_path.exists():
        return ass_path

    entries = _parse_srt_entries(srt_path.read_text(encoding="utf-8"))
    word_timings = []
    for entry in entries:
        words = entry["text"].split()
        if not words:
            continue
        duration = max(entry["end"] - entry["start"], 0.2)
        word_duration = duration / len(words)
        for index, word in enumerate(words):
            start = entry["start"] + (index * word_duration)
            end = start + word_duration
            word_timings.append(WordTiming(start_seconds=start, end_seconds=end, text=word))

    return build_ass_subtitles(word_timings, ass_path, play_res_x=play_res_x, play_res_y=play_res_y)


def _build_ass_header(play_res_x: int, play_res_y: int) -> str:
    is_portrait = play_res_y > play_res_x
    font_size = 58 if is_portrait else 46
    margin_vertical = 160 if is_portrait else 90
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans Bold,{font_size},&H00FFFFFF,&H0000D7FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,1,2,80,80,{margin_vertical},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _group_words_into_chunks(word_timings: list[WordTiming], words_per_line: int) -> list[list[WordTiming]]:
    chunks: list[list[WordTiming]] = []
    for index in range(0, len(word_timings), words_per_line):
        chunk = word_timings[index : index + words_per_line]
        if chunk:
            chunks.append(chunk)
    return chunks


def _build_karaoke_dialogue(chunk: list[WordTiming]) -> str:
    start = _format_ass_timestamp(chunk[0].start_seconds)
    end = _format_ass_timestamp(chunk[-1].end_seconds)
    karaoke_parts = []
    for word in chunk:
        duration_cs = max(int((word.end_seconds - word.start_seconds) * 100), 1)
        cleaned = word.text.replace("{", "").replace("}", "")
        karaoke_parts.append(f"{{\\k{duration_cs}}}{cleaned}")
    return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{' '.join(karaoke_parts)}"


def _format_ass_timestamp(seconds: float) -> str:
    total_cs = int(seconds * 100)
    hours = total_cs // 360000
    minutes = (total_cs % 360000) // 6000
    secs = (total_cs % 6000) // 100
    cs = total_cs % 100
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _parse_srt_entries(srt_content: str) -> list[dict]:
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    entries: list[dict] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        timing_line = lines[1] if "-->" in lines[1] else lines[0]
        text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
        if "-->" not in timing_line:
            continue
        start_raw, end_raw = [part.strip() for part in timing_line.split("-->")]
        entries.append({
            "start": _parse_srt_timestamp(start_raw),
            "end": _parse_srt_timestamp(end_raw),
            "text": " ".join(text_lines),
        })
    return entries


def _parse_srt_timestamp(timestamp: str) -> float:
    hours, minutes, rest = timestamp.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000.0
