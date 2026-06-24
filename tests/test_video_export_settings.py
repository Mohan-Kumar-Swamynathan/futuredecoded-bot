"""Tests for CI-aware video export settings and scene limits."""

from futuredecoded.media.scene_planner import _calculate_scene_durations, _merge_scene_durations_to_limit
from futuredecoded.media.video_export_settings import (
    export_fps,
    is_ci_build,
    max_scene_count,
    skip_finalize_reencode,
    use_lightweight_motion,
)


def test_ci_export_profile_activates_in_github_actions(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("USE_CINEMATIC_RENDERER", "true")
    assert is_ci_build() is True
    assert export_fps() == 24
    assert use_lightweight_motion() is True
    assert max_scene_count() == 22
    assert max_scene_count(is_short_form=True) == 6
    assert skip_finalize_reencode() is False


def test_ci_ken_burns_profile_keeps_scene_cap(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("USE_CINEMATIC_RENDERER", "false")
    assert max_scene_count() == 12


def test_merge_scene_durations_to_limit_reduces_scene_count():
    durations = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
    merged = _merge_scene_durations_to_limit(durations, scene_limit=3, max_scene_seconds=10.0)
    assert len(merged) == 3
    assert round(sum(merged), 2) == round(sum(durations), 2)
    assert max(merged) <= 10.0


def test_merge_scene_durations_keeps_scenes_when_even_split_exceeds_cap():
    durations = [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    merged = _merge_scene_durations_to_limit(durations, scene_limit=3, max_scene_seconds=5.0)
    assert len(merged) == 6


def test_calculate_scene_durations_caps_scene_count_for_shorts_in_ci(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("USE_CINEMATIC_RENDERER", "true")
    durations = _calculate_scene_durations(49.0, is_short_form=True)
    assert len(durations) <= 6
    assert round(sum(durations), 1) == 49.0


def test_calculate_scene_durations_limits_long_form_scene_count_in_ci(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("USE_CINEMATIC_RENDERER", "true")
    durations = _calculate_scene_durations(198.5)
    assert len(durations) <= 22
    assert max(durations) <= 14.0
    assert round(sum(durations), 1) == 198.5
