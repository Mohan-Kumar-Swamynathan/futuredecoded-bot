"""Tests for cinematic renderer helpers."""

from futuredecoded.media.caption_engine import WordTiming
from futuredecoded.media.cinematic_renderer import _count_visible_words, load_word_timings


def test_count_visible_words_respects_end_time():
    timings = [
        WordTiming(start_seconds=0.0, end_seconds=0.4, text="OpenAI"),
        WordTiming(start_seconds=0.4, end_seconds=0.8, text="launches"),
        WordTiming(start_seconds=0.8, end_seconds=1.2, text="GPT-5"),
    ]
    assert _count_visible_words(timings, 0.41) == 1
    assert _count_visible_words(timings, 0.75) == 1
    assert _count_visible_words(timings, 0.85) == 2


def test_load_word_timings_reads_json(tmp_path):
    timing_path = tmp_path / "voice.word_timings.json"
    timing_path.write_text(
        '[{"start_seconds": 0.0, "end_seconds": 0.5, "text": "Hello"}]',
        encoding="utf-8",
    )
    timings = load_word_timings(timing_path)
    assert len(timings) == 1
    assert timings[0].text == "Hello"
