"""Tests for caption engine."""

from pathlib import Path

from futuredecoded.media.caption_engine import WordTiming, build_ass_subtitles


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
