"""Tests for BGM mixing."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from futuredecoded.media.audio_mixer import mix_narration_with_bgm, resolve_bgm_track


@patch("futuredecoded.media.audio_mixer.subprocess.run")
@patch("futuredecoded.media.audio_mixer.get_settings")
@patch("futuredecoded.media.audio_mixer.get_audio_duration", return_value=30.0)
def test_mix_narration_with_bgm_uses_ffmpeg_amix(
    _mock_duration,
    mock_settings,
    mock_run,
    tmp_path: Path,
):
    settings = MagicMock()
    bgm_path = tmp_path / "bgm.mp3"
    bgm_path.write_bytes(b"bgm")
    settings.assets_dir = tmp_path
    mock_settings.return_value = settings

    mock_run.return_value = MagicMock(returncode=0)
    narration_path = tmp_path / "narration.mp3"
    narration_path.write_bytes(b"voice")
    output_path = tmp_path / "mixed.mp3"

    with patch("futuredecoded.media.audio_mixer.resolve_bgm_track", return_value=bgm_path):
        result = mix_narration_with_bgm(narration_path, output_path, format_type="long")

    assert result == output_path
    command = mock_run.call_args.args[0]
    assert "amix=inputs=2" in command[command.index("-filter_complex") + 1]


@patch("futuredecoded.media.audio_mixer._generate_fallback_bgm")
def test_resolve_bgm_track_uses_custom_asset_when_present(mock_generate, tmp_path: Path):
    bgm_dir = tmp_path / "bgm"
    bgm_dir.mkdir(parents=True)
    custom_track = bgm_dir / "long_form.mp3"
    custom_track.write_bytes(b"custom")

    resolved = resolve_bgm_track("long", tmp_path, duration=60.0)

    assert resolved == custom_track
    mock_generate.assert_not_called()


@patch("futuredecoded.media.audio_mixer._generate_fallback_bgm")
@patch("futuredecoded.media.audio_mixer.get_audio_duration", return_value=0.0)
def test_resolve_bgm_track_generates_auto_bgm_when_no_custom_file(
    _mock_duration,
    mock_generate,
    tmp_path: Path,
):
    generated = tmp_path / "bgm" / "long_form_auto.mp3"
    mock_generate.return_value = generated

    resolved = resolve_bgm_track("long", tmp_path, duration=240.0)

    assert resolved == generated
    mock_generate.assert_called_once()
