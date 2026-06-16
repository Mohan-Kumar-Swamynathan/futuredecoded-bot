"""Runtime video export profile — lighter settings in GitHub Actions CI."""

from __future__ import annotations

import os


def is_ci_build() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


def export_fps() -> int:
    return 24 if is_ci_build() else 30


def ffmpeg_preset() -> str:
    return "ultrafast" if is_ci_build() else "veryfast"


def ffmpeg_crf() -> str:
    return "28" if is_ci_build() else "22"


def ffmpeg_thread_count() -> int:
    return 2 if is_ci_build() else 0


def max_scene_duration_seconds() -> float:
    return 12.0 if is_ci_build() else 5.0


def min_scene_duration_seconds() -> float:
    return 8.0 if is_ci_build() else 3.0


def default_scene_duration_seconds() -> float:
    return 10.0 if is_ci_build() else 4.0


def hook_scene_duration_seconds() -> float:
    return 8.0 if is_ci_build() else 3.0


def hook_window_seconds() -> float:
    return 15.0


def use_lightweight_motion() -> bool:
    return is_ci_build()


def skip_segment_enhancements() -> bool:
    """Skip vignette, fade, and color grading in CI."""
    return is_ci_build()


def skip_text_overlays() -> bool:
    return is_ci_build()


def use_concat_stream_copy() -> bool:
    """Concat scene clips without re-encoding."""
    return is_ci_build()


def skip_finalize_reencode() -> bool:
    """Skip full-length caption/watermark re-encode in CI (uses YouTube auto-captions)."""
    return is_ci_build()


def run_black_frame_detection() -> bool:
    return not is_ci_build()


def require_burned_captions() -> bool:
    return not is_ci_build()


def max_scene_count() -> int | None:
    return 12 if is_ci_build() else None


def parallel_segment_workers() -> int:
    return 2 if is_ci_build() else 1


def segment_render_timeout_seconds() -> int:
    return 90 if is_ci_build() else 300


def finalize_render_timeout_seconds() -> int:
    return 600 if is_ci_build() else 600
