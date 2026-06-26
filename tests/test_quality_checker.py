"""Tests for export quality checks."""

from pathlib import Path
from unittest.mock import patch

from futuredecoded.media.quality_checker import validate_video_output


def test_cinematic_ci_profile_allows_longer_scene_durations(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("USE_CINEMATIC_RENDERER", "true")

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"\x00" * 1024)

    with patch("futuredecoded.media.quality_checker._has_audio_stream", return_value=True):
        report = validate_video_output(
            video_path=video_path,
            caption_path=None,
            scene_durations=[32.5, 32.5, 32.5],
            is_short_form=False,
        )
    assert report.passed is True
    assert not any("exceeds limit" in issue for issue in report.issues)
