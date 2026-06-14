"""YouTube chapter builder — timestamps derived from actual script + duration."""

from __future__ import annotations

from dataclasses import dataclass

LONG_FORM_CHAPTER_LABELS = (
    "Hook",
    "Background",
    "The News",
    "Analysis",
    "Future Impact",
    "Wrap Up",
)

SHORT_FORM_CHAPTER_LABELS = (
    "Hook",
    "What Happened",
    "Why It Matters",
    "Takeaway",
)


@dataclass(frozen=True)
class VideoChapter:
    time: str
    label: str
    start_seconds: float


def format_chapter_timestamp(total_seconds: float) -> str:
    bounded_seconds = max(0, int(total_seconds))
    hours = bounded_seconds // 3600
    minutes = (bounded_seconds % 3600) // 60
    seconds = bounded_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _word_count(section: dict) -> int:
    return max(1, len(str(section.get("text", "")).split()))


def _fallback_sections(script_text: str, labels: tuple[str, ...]) -> list[dict[str, str]]:
    words = script_text.split()
    if not words:
        return [{"label": label, "text": ""} for label in labels[:3]]

    chunk_size = max(1, len(words) // len(labels))
    sections: list[dict[str, str]] = []
    for index, label in enumerate(labels):
        start = index * chunk_size
        end = (index + 1) * chunk_size if index < len(labels) - 1 else len(words)
        chunk_words = words[start:end]
        if chunk_words:
            sections.append({"label": label, "text": " ".join(chunk_words)})
    return sections or [{"label": labels[0], "text": script_text}]


def build_chapters_from_sections(
    sections: list[dict[str, str]],
    duration_seconds: float,
    *,
    fallback_script: str = "",
    format_type: str = "long",
) -> list[VideoChapter]:
    if duration_seconds < 30:
        return []

    label_defaults = LONG_FORM_CHAPTER_LABELS if format_type == "long" else SHORT_FORM_CHAPTER_LABELS
    resolved_sections = sections or _fallback_sections(fallback_script, label_defaults)

    total_words = sum(_word_count(section) for section in resolved_sections)
    chapters: list[VideoChapter] = []
    word_offset = 0

    for index, section in enumerate(resolved_sections):
        label = str(section.get("label", label_defaults[min(index, len(label_defaults) - 1)])).strip()
        start_seconds = 0.0 if index == 0 else duration_seconds * (word_offset / total_words)
        chapters.append(
            VideoChapter(
                time=format_chapter_timestamp(start_seconds),
                label=label,
                start_seconds=start_seconds,
            )
        )
        word_offset += _word_count(section)

    return _enforce_youtube_chapter_rules(chapters, duration_seconds)


def _enforce_youtube_chapter_rules(
    chapters: list[VideoChapter],
    duration_seconds: float,
) -> list[VideoChapter]:
    if not chapters:
        return []

    chapters[0] = VideoChapter("0:00", chapters[0].label, 0.0)
    minimum_gap_seconds = 10.0
    validated: list[VideoChapter] = [chapters[0]]

    for chapter in chapters[1:]:
        if chapter.start_seconds - validated[-1].start_seconds >= minimum_gap_seconds:
            validated.append(chapter)

    if len(validated) < 3:
        validated = _build_equal_chapters(duration_seconds, chapter_count=3)

    if len(validated) < 3:
        return []

    validated[0] = VideoChapter("0:00", validated[0].label, 0.0)
    return validated


def _build_equal_chapters(duration_seconds: float, chapter_count: int) -> list[VideoChapter]:
    labels = list(LONG_FORM_CHAPTER_LABELS[:chapter_count])
    interval = duration_seconds / chapter_count
    return [
        VideoChapter(
            time=format_chapter_timestamp(index * interval),
            label=labels[index],
            start_seconds=index * interval,
        )
        for index in range(chapter_count)
    ]
