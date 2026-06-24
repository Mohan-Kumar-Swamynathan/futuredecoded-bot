"""Per-scene English visual briefs for stock video search."""

from __future__ import annotations

from dataclasses import dataclass

from futuredecoded.config.visual_style import VisualStyle, classify_section_visual_style, style_query_suffix
from futuredecoded.media.visual_keywords import (
    build_section_search_keywords,
    build_section_visual_prompt,
)


@dataclass(frozen=True)
class SceneVisualPlan:
    section_label: str
    section_text: str
    image_search_prompt: str
    search_keywords: tuple[str, ...]
    visual_style: str


def build_scene_visual_plans(
    sections: list[dict[str, str]],
    story_title: str,
) -> list[SceneVisualPlan]:
    """Build one visual plan per script section."""
    if not sections:
        return [
            SceneVisualPlan(
                section_label="Story",
                section_text=story_title,
                image_search_prompt=build_section_visual_prompt("Story", story_title, story_title),
                search_keywords=tuple(build_section_search_keywords("Story", story_title, story_title)),
                visual_style=VisualStyle.REAL_FOOTAGE.value,
            )
        ]

    plans: list[SceneVisualPlan] = []
    for section in sections:
        label = str(section.get("label", "Scene")).strip() or "Scene"
        text = str(section.get("text", "")).strip()
        visual_style = str(section.get("visual_style", "")).strip()
        if visual_style not in {VisualStyle.REAL_FOOTAGE.value, VisualStyle.MOTION_GRAPHICS.value}:
            visual_style = classify_section_visual_style(label, text).value

        image_prompt = str(section.get("image_search_prompt", "")).strip()
        if not image_prompt:
            image_prompt = build_section_visual_prompt(label, text, story_title, visual_style)

        keywords = section.get("search_keywords") or build_section_search_keywords(
            label,
            text,
            story_title,
            visual_style,
            image_prompt,
        )
        keyword_tuple = tuple(keyword.strip() for keyword in keywords if str(keyword).strip())[:4]
        if not keyword_tuple:
            keyword_tuple = (image_prompt,)

        plans.append(
            SceneVisualPlan(
                section_label=label,
                section_text=text,
                image_search_prompt=image_prompt,
                search_keywords=keyword_tuple,
                visual_style=visual_style,
            )
        )
    return plans


def enrich_sections_with_visual_metadata(
    sections: list[dict[str, str]],
    story_title: str,
) -> list[dict[str, str]]:
    """Attach image_search_prompt and search_keywords to section dicts."""
    plans = build_scene_visual_plans(sections, story_title)
    enriched: list[dict[str, str]] = []
    for section, plan in zip(sections, plans):
        enriched.append(
            {
                **section,
                "image_search_prompt": plan.image_search_prompt,
                "search_keywords": list(plan.search_keywords),
                "visual_style": plan.visual_style,
            }
        )
    return enriched
