"""Tests for chapter builder and description formatter."""

from futuredecoded.seo.chapter_builder import VideoChapter, build_chapters_from_sections, format_chapter_timestamp
from futuredecoded.seo.description_formatter import build_long_form_description, normalize_multiline_text


def test_format_chapter_timestamp():
    assert format_chapter_timestamp(0) == "0:00"
    assert format_chapter_timestamp(90) == "1:30"


def test_build_chapters_from_sections_uses_word_proportions():
    sections = [
        {"label": "Hook", "text": "one two three four"},
        {"label": "Background", "text": "five six seven eight nine ten"},
        {"label": "Analysis", "text": "eleven twelve thirteen fourteen"},
    ]
    chapters = build_chapters_from_sections(sections, duration_seconds=120.0, format_type="long")
    assert len(chapters) >= 3
    assert chapters[0].time == "0:00"
    assert chapters[0].label == "Hook"
    assert chapters[1].start_seconds > 10


def test_normalize_multiline_text_converts_literal_newlines():
    raw = "Line one.\\n\\nLine two."
    cleaned = normalize_multiline_text(raw)
    assert "\\n" not in cleaned
    assert "Line one." in cleaned
    assert "Line two." in cleaned


def test_build_long_form_description_has_real_line_breaks():
    description = build_long_form_description(
        intro="Amazon CEO met with U.S. officials.",
        key_points=["Regulatory pressure increased", "Anthropic models affected"],
        chapters=[
            VideoChapter("0:00", "Hook", 0.0),
            VideoChapter("1:30", "Background", 90.0),
            VideoChapter("3:00", "Analysis", 180.0),
        ],
        sources=["https://example.com/source"],
        hashtags=["#AI", "#TechNews"],
    )
    assert "\\n" not in description
    assert "⏱ Chapters" in description
    assert "0:00 Hook" in description
    assert "📌 Key Points" in description
