"""Tests for pipeline output validation."""

from pathlib import Path
from unittest.mock import patch

from futuredecoded.config.channel_profile import ContentFormat
from futuredecoded.pipeline.orchestrator import _validate_pipeline_outputs


def test_validate_pipeline_outputs_requires_both_uploads():
    """Upload failures are non-fatal — function logs a warning and returns empty string."""
    with patch("futuredecoded.pipeline.orchestrator.logger") as mock_logger:
        error = _validate_pipeline_outputs(
            content_format=ContentFormat.BOTH,
            upload=True,
            long_video_path=Path("long.mp4"),
            short_video_path=Path("short.mp4"),
            long_video_id=None,
            short_video_id="abc",
        )
    # Non-fatal: returns empty string so pipeline continues
    assert error == ""
    # Warning must mention the missing upload
    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
    assert any("long-form upload" in c for c in warning_calls)


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
