"""Runtime video export profile — lighter settings in GitHub Actions CI."""

from __future__ import annotations

import os


def is_ci_build() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


def use_cinematic_renderer_enabled() -> bool:
    return os.getenv("USE_CINEMATIC_RENDERER", "true").lower() not in {"0", "false", "no", "off"}


def use_cinematic_export_profile() -> bool:
    return is_ci_build() and use_cinematic_renderer_enabled()


def export_fps() -> int:
    return 24 if is_ci_build() else 30


def ffmpeg_preset() -> str:
    return "veryfast" if is_ci_build() else "veryfast"


def ffmpeg_crf() -> str:
    return "22" if is_ci_build() else "21"


def ffmpeg_thread_count() -> int:
    return 2 if is_ci_build() else 0


def max_scene_duration_seconds(is_short_form: bool = False) -> float:
    if use_cinematic_export_profile():
        return 9.0 if is_short_form else 14.0
    return 30.0 if is_ci_build() else 5.0


def min_scene_duration_seconds() -> float:
    if use_cinematic_export_profile():
        return 4.0
    return 8.0 if is_ci_build() else 2.0


def default_scene_duration_seconds(is_short_form: bool = False) -> float:
    if use_cinematic_export_profile():
        return 5.0 if is_short_form else 10.0
    return 20.0 if is_ci_build() else 15.0


def hook_scene_duration_seconds(is_short_form: bool = False) -> float:
    if use_cinematic_export_profile():
        return 4.0 if is_short_form else 5.0
    return 5.0 if is_ci_build() else 3.0


def hook_window_seconds() -> float:
    return 15.0


def use_lightweight_motion() -> bool:
    return is_ci_build()


def skip_segment_enhancements() -> bool:
    return is_ci_build()


def skip_text_overlays() -> bool:
    return is_ci_build()


def use_concat_stream_copy() -> bool:
    if use_cinematic_export_profile():
        return False
    return is_ci_build()


def skip_finalize_reencode() -> bool:
    if use_cinematic_export_profile():
        return False
    return is_ci_build()


def run_black_frame_detection() -> bool:
    return not is_ci_build()


def require_burned_captions() -> bool:
    return not is_ci_build()


def max_scene_count(is_short_form: bool = False) -> int | None:
    if use_cinematic_export_profile():
        return 6 if is_short_form else 12
    return 12 if is_ci_build() else None


def parallel_segment_workers() -> int:
    if use_cinematic_export_profile():
        return 1
    return 3 if is_ci_build() else 1


def segment_render_timeout_seconds() -> int:
    return 180 if is_ci_build() else 300


def finalize_render_timeout_seconds() -> int:
    return 900 if is_ci_build() else 600
