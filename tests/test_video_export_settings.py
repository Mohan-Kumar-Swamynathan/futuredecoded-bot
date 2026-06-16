"""Tests for CI-aware video export settings and scene limits."""

from futuredecoded.media.scene_planner import _calculate_scene_durations, _merge_scene_durations_to_limit
from futuredecoded.media.video_export_settings import export_fps, is_ci_build, max_scene_count, skip_finalize_reencode, use_lightweight_motion


def test_ci_export_profile_activates_in_github_actions(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert is_ci_build() is True
    assert export_fps() == 24
    assert use_lightweight_motion() is True
    assert max_scene_count() == 12
    assert skip_finalize_reencode() is True


def test_merge_scene_durations_to_limit_reduces_scene_count():
    durations = [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    merged = _merge_scene_durations_to_limit(durations, scene_limit=3)
    assert len(merged) == 3
    assert round(sum(merged), 2) == round(sum(durations), 2)


def test_calculate_scene_durations_caps_scene_count_in_ci(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    durations = _calculate_scene_durations(198.5)
    assert len(durations) <= 12
    assert round(sum(durations), 1) == 198.5
