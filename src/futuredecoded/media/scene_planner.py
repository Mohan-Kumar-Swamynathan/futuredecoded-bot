"""Scene planner — 3-5 second visual cuts aligned to script sections."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

SCENE_DURATION_SECONDS = 4.0


@dataclass(frozen=True)
class VideoScene:
    section_label: str
    duration_seconds: float
    visual_query: str
    image_path: Path | None = None


def plan_video_scenes(
    sections: list[dict[str, str]],
    total_duration_seconds: float,
    story_title: str,
    image_paths: list[Path],
) -> list[VideoScene]:
    if total_duration_seconds <= 0:
        return []

    target_scene_count = max(3, math.ceil(total_duration_seconds / SCENE_DURATION_SECONDS))
    section_labels = [
        str(section.get("label", f"Scene {index + 1}"))
        for index, section in enumerate(sections)
    ] or ["Story"]

    scenes: list[VideoScene] = []
    for index in range(target_scene_count):
        section = sections[index % len(sections)] if sections else {"label": "Story", "text": story_title}
        label = section_labels[index % len(section_labels)]
        text_snippet = str(section.get("text", story_title))[:80]
        image_path = image_paths[index % len(image_paths)] if image_paths else None
        scenes.append(
            VideoScene(
                section_label=label,
                duration_seconds=SCENE_DURATION_SECONDS,
                visual_query=f"{label} {text_snippet}".strip(),
                image_path=image_path,
            )
        )

    remaining = total_duration_seconds - sum(scene.duration_seconds for scene in scenes)
    if scenes and remaining > 0:
        last_scene = scenes[-1]
        scenes[-1] = VideoScene(
            section_label=last_scene.section_label,
            duration_seconds=last_scene.duration_seconds + remaining,
            visual_query=last_scene.visual_query,
            image_path=last_scene.image_path,
        )
    return scenes
