"""Visual style classification for mixed stock footage + motion graphics."""

from __future__ import annotations

from enum import Enum

MOTION_GRAPHICS_LABELS = frozenset(
    {
        "hook",
        "technical depth",
        "your take",
        "why it matters",
        "cta",
        "call to action",
    }
)

MOTION_GRAPHICS_KEYWORDS = frozenset(
    {
        "ai",
        "algorithm",
        "neural",
        "model",
        "architecture",
        "benchmark",
        "compute",
        "chip",
        "gpu",
        "llm",
        "agent",
        "automation",
        "data",
        "cloud",
        "cyber",
        "security",
        "quantum",
    }
)


class VisualStyle(str, Enum):
    REAL_FOOTAGE = "real_footage"
    MOTION_GRAPHICS = "motion_graphics"


def classify_section_visual_style(section_label: str, section_text: str) -> VisualStyle:
    """Choose stock search style for a script section."""
    label_lower = section_label.lower().strip()
    text_lower = section_text.lower()

    if any(marker in label_lower for marker in MOTION_GRAPHICS_LABELS):
        return VisualStyle.MOTION_GRAPHICS
    if any(keyword in text_lower for keyword in MOTION_GRAPHICS_KEYWORDS):
        return VisualStyle.MOTION_GRAPHICS
    return VisualStyle.REAL_FOOTAGE


def style_query_suffix(visual_style: VisualStyle, section_label: str = "") -> str:
    """Return a short English modifier that keeps stock searches topic-specific."""
    label = section_label.lower().strip()
    if visual_style == VisualStyle.MOTION_GRAPHICS:
        if "hook" in label:
            return "technology news headline"
        if "technical" in label:
            return "data center server technology"
        if "industry" in label or "impact" in label:
            return "corporate business technology"
        if "take" in label or "opinion" in label:
            return "team discussion technology office"
        return "technology innovation"

    if "context" in label or "background" in label:
        return "news documentary footage"
    if "happened" in label or "story" in label:
        return "breaking news report"
    if "resolution" in label or "outcome" in label:
        return "business success professional"
    return "professional business"
