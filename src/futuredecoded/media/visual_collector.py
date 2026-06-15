"""Visual collector — story-relevant Pexels/Pixabay images."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from futuredecoded.config.settings import get_settings
from futuredecoded.media.visual_keywords import (
    build_visual_search_queries,
    score_image_relevance,
)

logger = logging.getLogger("futuredecoded.media.visuals")


@dataclass(frozen=True)
class VisualCandidate:
    path: Path
    query: str
    alt_text: str
    relevance_score: float


def collect_visuals_for_story(
    topic_slug: str,
    story_title: str,
    outline: dict | None = None,
    sections: list[dict[str, str]] | None = None,
    max_images: int = 8,
    orientation: str = "landscape",
) -> list[Path]:
    settings = get_settings()
    asset_dir = settings.assets_dir / topic_slug / orientation
    asset_dir.mkdir(parents=True, exist_ok=True)

    queries = build_visual_search_queries(story_title, outline, sections)
    candidates: list[VisualCandidate] = []

    if settings.pexels_api_key:
        candidates.extend(
            _fetch_pexels_candidates(queries, asset_dir, story_title, settings.pexels_api_key, orientation)
        )
    if len(candidates) < max_images and settings.pixabay_api_key:
        candidates.extend(
            _fetch_pixabay_candidates(
                queries,
                asset_dir,
                story_title,
                settings.pixabay_api_key,
                orientation,
            )
        )

    ranked_candidates = _rank_candidates(candidates, max_images)
    if len(ranked_candidates) < 3:
        ranked_candidates.extend(
            _generate_placeholder_images(asset_dir, max(3, max_images - len(ranked_candidates)), story_title)
        )

    image_paths = [candidate.path for candidate in ranked_candidates[:max_images]]
    logger.info(
        "Collected %d relevant %s visuals for %s (queries=%d)",
        len(image_paths),
        orientation,
        topic_slug,
        len(queries),
    )
    return image_paths


def collect_visuals(topic_slug: str, keywords: list[str], max_images: int = 8) -> list[Path]:
    return collect_visuals_for_story(
        topic_slug=topic_slug,
        story_title=" ".join(keywords),
        outline={"key_facts": keywords},
        max_images=max_images,
        orientation="landscape",
    )


def _rank_candidates(candidates: list[VisualCandidate], max_images: int) -> list[VisualCandidate]:
    unique_by_path: dict[str, VisualCandidate] = {}
    for candidate in candidates:
        path_key = str(candidate.path)
        existing = unique_by_path.get(path_key)
        if existing is None or candidate.relevance_score > existing.relevance_score:
            unique_by_path[path_key] = candidate

    ranked = sorted(unique_by_path.values(), key=lambda item: item.relevance_score, reverse=True)
    return ranked[:max_images]


def _fetch_pexels_candidates(
    queries: list[str],
    dest: Path,
    story_title: str,
    api_key: str,
    orientation: str,
) -> list[VisualCandidate]:
    candidates: list[VisualCandidate] = []
    headers = {"Authorization": api_key}

    for query in queries:
        try:
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": query, "per_page": 6, "orientation": orientation},
                timeout=15,
            )
            if response.status_code != 200:
                continue

            for photo in response.json().get("photos", []):
                image_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
                if not image_url:
                    continue

                file_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
                image_path = dest / f"pexels_{file_hash}.jpg"
                if not image_path.exists():
                    image_response = requests.get(image_url, timeout=20)
                    if image_response.status_code != 200:
                        continue
                    image_path.write_bytes(image_response.content)

                alt_text = str(photo.get("alt", "") or query)
                candidates.append(
                    VisualCandidate(
                        path=image_path,
                        query=query,
                        alt_text=alt_text,
                        relevance_score=score_image_relevance(story_title, alt_text, query),
                    )
                )
        except Exception as exc:
            logger.debug("Pexels query failed for '%s': %s", query, exc)

    return candidates


def _fetch_pixabay_candidates(
    queries: list[str],
    dest: Path,
    story_title: str,
    api_key: str,
    orientation: str,
) -> list[VisualCandidate]:
    candidates: list[VisualCandidate] = []
    orientation_param = "horizontal" if orientation == "landscape" else "vertical"

    for query in queries[:6]:
        try:
            response = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": orientation_param,
                    "per_page": 6,
                },
                timeout=15,
            )
            if response.status_code != 200:
                continue

            for hit in response.json().get("hits", []):
                image_url = hit.get("largeImageURL")
                if not image_url:
                    continue

                file_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
                image_path = dest / f"pixabay_{file_hash}.jpg"
                if not image_path.exists():
                    image_response = requests.get(image_url, timeout=20)
                    if image_response.status_code != 200:
                        continue
                    image_path.write_bytes(image_response.content)

                tags = str(hit.get("tags", "") or query)
                candidates.append(
                    VisualCandidate(
                        path=image_path,
                        query=query,
                        alt_text=tags,
                        relevance_score=score_image_relevance(story_title, tags, query),
                    )
                )
        except Exception as exc:
            logger.debug("Pixabay query failed for '%s': %s", query, exc)

    return candidates


def _generate_placeholder_images(dest: Path, count: int, story_title: str) -> list[VisualCandidate]:
    from PIL import Image, ImageDraw

    placeholders: list[VisualCandidate] = []
    colors = [(20, 30, 60), (30, 20, 50), (10, 40, 70)]
    headline = " ".join(story_title.split()[:6])

    for index in range(count):
        image_path = dest / f"placeholder_{index}.png"
        image = Image.new("RGB", (1920, 1080), colors[index % len(colors)])
        draw = ImageDraw.Draw(image)
        draw.text((80, 480), "FutureDecoded", fill=(255, 255, 255))
        draw.text((80, 540), headline[:60], fill=(200, 200, 220))
        image.save(image_path)
        placeholders.append(
            VisualCandidate(
                path=image_path,
                query=headline,
                alt_text=headline,
                relevance_score=0.1,
            )
        )

    return placeholders
