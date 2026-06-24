"""Tests for caption engine."""

from pathlib import Path

from futuredecoded.media.caption_engine import (
    WordTiming,
    build_ass_subtitles,
    build_scene_ass_subtitles,
    slice_word_timings_for_scene,
)


def test_build_ass_subtitles_creates_karaoke_dialogue(tmp_path: Path):
    word_timings = [
        WordTiming(0.0, 0.4, "OpenAI"),
        WordTiming(0.4, 0.8, "just"),
        WordTiming(0.8, 1.2, "launched"),
    ]
    ass_path = tmp_path / "captions.ass"
    build_ass_subtitles(word_timings, ass_path)

    content = ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "\\k" in content
    assert "OpenAI" in content


def test_slice_word_timings_for_scene_offsets_to_zero():
    timings = [
        WordTiming(0.0, 0.5, "One"),
        WordTiming(0.5, 1.0, "Two"),
        WordTiming(4.0, 4.5, "Three"),
    ]
    sliced = slice_word_timings_for_scene(timings, scene_start_seconds=0.5, scene_duration_seconds=2.0)
    assert len(sliced) == 1
    assert sliced[0].text == "Two"
    assert sliced[0].start_seconds == 0.0
    assert sliced[0].end_seconds == 0.5


def test_build_scene_ass_subtitles_writes_dialogue(tmp_path: Path):
    timings = [WordTiming(2.0, 2.4, "Future"), WordTiming(2.4, 2.8, "Decoded")]
    ass_path = tmp_path / "scene.ass"
    build_scene_ass_subtitles(timings, 2.0, 1.0, ass_path)
    content = ass_path.read_text(encoding="utf-8")
    assert "Future" in content
    assert "Decoded" in content
