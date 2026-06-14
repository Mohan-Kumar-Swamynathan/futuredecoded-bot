"""Edge TTS voice generation with SRT subtitles."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from futuredecoded.config.channel_profile import EDGE_TTS_PITCH, EDGE_TTS_RATE, EDGE_TTS_VOICE

logger = logging.getLogger("futuredecoded.media.voice")


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _generate_srt(script_text: str, duration: float, words_per_segment: int = 12) -> str:
    words = script_text.split()
    segments = [" ".join(words[index:index + words_per_segment])
                for index in range(0, len(words), words_per_segment)]
    if not segments:
        return ""
    sec_per = duration / len(segments)
    lines: list[str] = []
    for index, segment in enumerate(segments):
        start = index * sec_per
        end = (index + 1) * sec_per
        lines += [
            str(index + 1),
            f"{_ts(start)} --> {_ts(end)}",
            segment,
            "",
        ]
    return "\n".join(lines)


def _ts(seconds: float) -> str:
    total_seconds = int(seconds)
    millis = int((seconds - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def synthesise_voice(script_text: str, output_path: Path) -> tuple[Path, float]:
    if not shutil.which("edge-tts"):
        raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        script_file = Path(temp_dir) / "script.txt"
        script_file.write_text(script_text, encoding="utf-8")
        subprocess.run(
            [
                "edge-tts",
                "--file", str(script_file),
                "--voice", EDGE_TTS_VOICE,
                "--rate", EDGE_TTS_RATE,
                "--pitch", EDGE_TTS_PITCH,
                "--write-media", str(output_path),
            ],
            check=True, capture_output=True, timeout=600,
        )

    duration = get_audio_duration(output_path)
    srt_path = output_path.with_suffix(".srt")
    srt_path.write_text(_generate_srt(script_text, duration), encoding="utf-8")
    logger.info("Voice synthesised: %s (%.1fs)", output_path.name, duration)
    return output_path, duration
