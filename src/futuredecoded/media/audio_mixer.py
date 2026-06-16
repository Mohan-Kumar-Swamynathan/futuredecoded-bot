"""Background music resolver and narration mixer."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from futuredecoded.config.channel_profile import (
    BGM_FILENAME_LONG,
    BGM_FILENAME_SHORT,
    BGM_MUSIC_VOLUME_LONG,
    BGM_MUSIC_VOLUME_SHORT,
)
from futuredecoded.config.settings import get_settings
from futuredecoded.media.audio_utils import get_audio_duration

logger = logging.getLogger("futuredecoded.media.audio_mixer")


def mix_narration_with_bgm(
    narration_path: Path,
    output_path: Path,
    format_type: str = "long",
) -> Path:
    """Mix narration with background music at a low, ducking-safe volume."""
    narration_duration = get_audio_duration(narration_path)
    if narration_duration <= 0:
        raise RuntimeError(f"Invalid narration duration: {narration_path}")

    settings = get_settings()
    bgm_path = resolve_bgm_track(format_type=format_type, assets_dir=settings.assets_dir, duration=narration_duration)
    music_volume = BGM_MUSIC_VOLUME_LONG if format_type == "long" else BGM_MUSIC_VOLUME_SHORT

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Sidechain compress BGM under voice — much more natural than plain mix
    # Voice EQ: natural warmth, room presence, light compression
    filter_graph = (
        f"[0:a]highpass=f=85,"
        f"equalizer=f=180:t=q:w=0.9:g=1.5,"
        f"equalizer=f=1000:t=q:w=0.8:g=1.5,"
        f"equalizer=f=7000:t=q:w=1:g=-1.5,"
        f"aecho=0.72:0.58:22|40:0.06|0.03,"
        f"acompressor=threshold=-20dB:ratio=1.6:attack=10:release=300:makeup=1.5,"
        f"loudnorm=I=-14:TP=-1.5:LRA=12,asplit=2[voice][sc];"
        f"[1:a]volume={music_volume},aloop=loop=-1:size=2e+09[bgm];"
        f"[bgm][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=500[bgm_ducked];"
        f"[voice][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(narration_path),
        "-i",
        str(bgm_path),
        "-filter_complex",
        filter_graph,
        "-map",
        "[aout]",
        "-t",
        f"{narration_duration:.2f}",
        "-c:a",
        "libmp3lame",
        "-qscale:a",
        "2",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"BGM mix failed: {result.stderr[-300:]}")

    logger.info(
        "Mixed narration with BGM (%s, music=%.0f%%): %s",
        format_type,
        music_volume * 100,
        output_path.name,
    )
    return output_path


def resolve_bgm_track(format_type: str, assets_dir: Path, duration: float) -> Path:
    bgm_dir = assets_dir / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    filename = BGM_FILENAME_LONG if format_type == "long" else BGM_FILENAME_SHORT
    custom_track = bgm_dir / filename

    if custom_track.exists() and custom_track.stat().st_size > 0:
        logger.info("Using custom BGM track: %s", custom_track.name)
        return custom_track

    # No custom files needed — reuse a cached auto-generated ambient bed.
    generated_track = bgm_dir / f"{custom_track.stem}_auto.mp3"
    cached_duration = get_audio_duration(generated_track)
    if generated_track.exists() and cached_duration >= 60.0:
        logger.info("Using auto-generated BGM (no custom file required): %s", generated_track.name)
        return generated_track

    return _generate_fallback_bgm(generated_track, duration=360.0)


def _generate_fallback_bgm(output_path: Path, duration: float) -> Path:
    """Generate a subtle ambient bed — used automatically when no custom BGM is provided."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anoisesrc=color=pink:duration={duration:.2f}:sample_rate=44100:amplitude=0.015",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=82.41:duration={duration:.2f}:sample_rate=44100",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=123.47:duration={duration:.2f}:sample_rate=44100",
        "-filter_complex",
        (
            "[0:a][1:a][2:a]amix=inputs=3:duration=first,"
            "volume=0.18,lowpass=f=700,highpass=f=90,afade=t=in:st=0:d=3,afade=t=out:st="
            f"{max(duration - 4, 0):.2f}:d=4[aout]"
        ),
        "-map",
        "[aout]",
        "-c:a",
        "libmp3lame",
        "-qscale:a",
        "9",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"Fallback BGM generation failed: {result.stderr[-300:]}")
    logger.info("Generated fallback BGM track: %s (%.1fs)", output_path.name, duration)
    return output_path
