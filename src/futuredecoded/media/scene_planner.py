"""Scene planner — 3-5s cuts, motion types, hook pacing, overlay metadata."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from futuredecoded.media.video_export_settings import (
    default_scene_duration_seconds,
    hook_scene_duration_seconds,
    hook_window_seconds,
    max_scene_count,
    max_scene_duration_seconds,
    min_scene_duration_seconds,
)

ANIMATION_CYCLE = ("zoom_in", "zoom_out", "pan_left", "pan_right")

# Backwards-compatible constants for tests and quality checks.
MAX_SCENE_DURATION_SECONDS = 5.0
MIN_SCENE_DURATION_SECONDS = 3.0
DEFAULT_SCENE_DURATION_SECONDS = 4.0
HOOK_WINDOW_SECONDS = 15.0
HOOK_SCENE_DURATION_SECONDS = 3.0


class AnimationType(str, Enum):
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"


@dataclass(frozen=True)
class VideoScene:
    section_label: str
    duration_seconds: float
    visual_query: str
    image_path: Path | None = None
    animation_type: str = AnimationType.ZOOM_IN.value
    text_overlay: str | None = None
    is_hook_scene: bool = False
    scene_description: str = ""


def plan_video_scenes(
    sections: list[dict[str, str]],
    total_duration_seconds: float,
    story_title: str,
    image_paths: list[Path],
) -> list[VideoScene]:
    if total_duration_seconds <= 0:
        return []

    scene_durations = _calculate_scene_durations(total_duration_seconds)
    deduped_images = _dedupe_image_order(image_paths, len(scene_durations))
    scenes: list[VideoScene] = []

    for index, duration in enumerate(scene_durations):
        section = sections[index % len(sections)] if sections else {"label": "Story", "text": story_title}
        label = str(section.get("label", f"Scene {index + 1}"))
        section_text = str(section.get("text", story_title)).strip()
        elapsed_before_scene = sum(scene_durations[:index])
        is_hook = elapsed_before_scene < hook_window_seconds()
        overlay_text = _extract_overlay_text(section_text, story_title) if is_hook or index % 5 == 0 else None
        if is_hook and not overlay_text:
            overlay_text = _extract_overlay_text(story_title, story_title)

        image_path = deduped_images[index % len(deduped_images)] if deduped_images else None
        scenes.append(
            VideoScene(
                section_label=label,
                duration_seconds=duration,
                visual_query=f"{label} {section_text[:80]}".strip(),
                image_path=image_path,
                animation_type=ANIMATION_CYCLE[index % len(ANIMATION_CYCLE)],
                text_overlay=overlay_text,
                is_hook_scene=is_hook,
                scene_description=section_text[:160],
            )
        )

    return scenes


def export_scene_manifest(scenes: list[VideoScene], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "section_label": scene.section_label,
            "duration_seconds": scene.duration_seconds,
            "animation_type": scene.animation_type,
            "text_overlay": scene.text_overlay,
            "is_hook_scene": scene.is_hook_scene,
            "visual_query": scene.visual_query,
            "scene_description": scene.scene_description,
            "image_path": str(scene.image_path) if scene.image_path else None,
        }
        for scene in scenes
    ]
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _calculate_scene_durations(total_duration_seconds: float) -> list[float]:
    durations: list[float] = []
    elapsed = 0.0
    hook_window = hook_window_seconds()
    hook_scene = hook_scene_duration_seconds()
    default_scene = default_scene_duration_seconds()
    max_scene = max_scene_duration_seconds()
    min_scene = min_scene_duration_seconds()

    while elapsed < total_duration_seconds - 0.25:
        remaining = total_duration_seconds - elapsed
        if elapsed < hook_window:
            duration = min(hook_scene, remaining, max_scene)
        else:
            duration = min(default_scene, remaining, max_scene)
        duration = max(min(duration, max_scene), min(min_scene, remaining))
        if remaining < min_scene:
            duration = remaining
        durations.append(round(duration, 2))
        elapsed += duration

    if durations and elapsed < total_duration_seconds:
        durations[-1] = round(durations[-1] + (total_duration_seconds - elapsed), 2)

    scene_limit = max_scene_count()
    if scene_limit is not None and len(durations) > scene_limit:
        durations = _merge_scene_durations_to_limit(durations, scene_limit)
    return durations


def _merge_scene_durations_to_limit(durations: list[float], scene_limit: int) -> list[float]:
    merged = durations.copy()
    max_scene = max_scene_duration_seconds()

    while len(merged) > scene_limit:
        merge_index = 0
        smallest_pair_sum = merged[0] + merged[1]
        for index in range(len(merged) - 1):
            pair_sum = merged[index] + merged[index + 1]
            if pair_sum <= max_scene * 1.5 and pair_sum < smallest_pair_sum:
                merge_index = index
                smallest_pair_sum = pair_sum
        merged[merge_index] = round(merged[merge_index] + merged[merge_index + 1], 2)
        del merged[merge_index + 1]

    return merged


def _dedupe_image_order(image_paths: list[Path], scene_count: int) -> list[Path]:
    usable = [path for path in image_paths if path and path.exists()]
    if not usable:
        return []

    ordered: list[Path] = []
    last_image: Path | None = None
    image_index = 0

    while len(ordered) < scene_count:
        candidate = usable[image_index % len(usable)]
        if last_image is not None and candidate == last_image and len(usable) > 1:
            image_index += 1
            candidate = usable[image_index % len(usable)]
        ordered.append(candidate)
        last_image = candidate
        image_index += 1

    return ordered


def _extract_overlay_text(section_text: str, story_title: str) -> str | None:
    combined = f"{story_title} {section_text}"
    uppercase_tokens = re.findall(r"\b[A-Z][A-Z0-9\-]{1,}\b", combined)
    if uppercase_tokens:
        return uppercase_tokens[0][:28]

    money_match = re.search(r"(\$[\d,.]+(?:\s?(?:billion|million|B|M))?)", combined, flags=re.IGNORECASE)
    if money_match:
        return money_match.group(1).upper()[:28]

    number_match = re.search(r"\b(\d+(?:\.\d+)?\s?(?:million|billion|%))\b", combined, flags=re.IGNORECASE)
    if number_match:
        return number_match.group(1).upper()[:28]

    entity_match = re.search(
        r"\b(OpenAI|Anthropic|Google|Gemini|GPT-\d+|Claude|Tesla|NVIDIA|Meta|Microsoft|Amazon)\b",
        combined,
        flags=re.IGNORECASE,
    )
    if entity_match:
        return entity_match.group(1).upper()[:28]

    headline_words = [word for word in re.findall(r"[A-Za-z0-9]+", story_title) if len(word) > 2][:4]
    if headline_words:
        return " ".join(headline_words).upper()[:28]

    return None
