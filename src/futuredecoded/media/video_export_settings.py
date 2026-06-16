"""Runtime video export profile — lighter settings in GitHub Actions CI."""

from __future__ import annotations

import os


def is_ci_build() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


def export_fps() -> int:
    return 24 if is_ci_build() else 30


def ffmpeg_preset() -> str:
    return "veryfast" if is_ci_build() else "veryfast"


def ffmpeg_crf() -> str:
    return "23" if is_ci_build() else "21"


def ffmpeg_thread_count() -> int:
    return 2 if is_ci_build() else 0


def max_scene_duration_seconds() -> float:
    # CI: 30s max — enough for a proper Ken Burns motion without timeout
    # Local: 25s — good balance for long-form
    return 30.0 if is_ci_build() else 5.0


def min_scene_duration_seconds() -> float:
    return 8.0 if is_ci_build() else 2.0


def default_scene_duration_seconds() -> float:
    # CI: 20s default — fewer scenes = less ffmpeg work = faster
    # Local: 15s default
    return 20.0 if is_ci_build() else 15.0


def hook_scene_duration_seconds() -> float:
    # Hook is first 15s — keep it snappy
    return 5.0 if is_ci_build() else 3.0


def hook_window_seconds() -> float:
    return 15.0


def use_lightweight_motion() -> bool:
    # CI: use lightweight motion to avoid zoompan timeout on slow runners
    return is_ci_build()


def skip_segment_enhancements() -> bool:
    """Skip vignette, fade, and color grading in CI — saves significant time."""
    return is_ci_build()


def skip_text_overlays() -> bool:
    return is_ci_build()


def use_concat_stream_copy() -> bool:
    """Concat scene clips without re-encoding — critical for CI speed."""
    return is_ci_build()


def skip_finalize_reencode() -> bool:
    """Skip full-length caption/watermark re-encode in CI (YouTube auto-captions from audio)."""
    return is_ci_build()


def run_black_frame_detection() -> bool:
    return not is_ci_build()


def require_burned_captions() -> bool:
    return not is_ci_build()


def max_scene_count() -> int | None:
    # CI: cap at 15 scenes — enough for 4-6 min video at 20s/scene
    return 12 if is_ci_build() else None


def parallel_segment_workers() -> int:
    # CI: 3 parallel workers — GitHub Actions has 2 vCPUs, 3 is fine
    return 3 if is_ci_build() else 1


def segment_render_timeout_seconds() -> int:
    # Each scene is max 30s — give 3× buffer = 90s per scene
    return 120 if is_ci_build() else 300


def finalize_render_timeout_seconds() -> int:
    # Full video concat + mux — give generous timeout
    return 900 if is_ci_build() else 600
