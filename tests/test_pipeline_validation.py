"""Tests for pipeline output validation."""

from pathlib import Path
from unittest.mock import patch

from futuredecoded.config.channel_profile import ContentFormat
from futuredecoded.pipeline.orchestrator import _validate_pipeline_outputs


def test_validate_pipeline_outputs_requires_both_uploads():
    error = _validate_pipeline_outputs(
        content_format=ContentFormat.BOTH,
        upload=True,
        long_video_path=Path("long.mp4"),
        short_video_path=Path("short.mp4"),
        long_video_id=None,
        short_video_id="abc",
    )
    assert "long-form upload" in error


def test_validate_pipeline_outputs_passes_when_both_present():
    error = _validate_pipeline_outputs(
        content_format=ContentFormat.BOTH,
        upload=True,
        long_video_path=Path("long.mp4"),
        short_video_path=Path("short.mp4"),
        long_video_id="long",
        short_video_id="short",
    )
    assert error == ""
