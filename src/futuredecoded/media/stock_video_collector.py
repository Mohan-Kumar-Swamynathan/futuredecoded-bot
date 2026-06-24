"""Fetch landscape/portrait stock clips from Pexels and Pixabay."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from futuredecoded.config.settings import get_settings
from futuredecoded.config.visual_style import VisualStyle
from futuredecoded.media.scene_visual_planner import SceneVisualPlan
from futuredecoded.media.visual_keywords import score_video_tag_relevance

logger = logging.getLogger(__name__)

PIXABAY_VIDEO_SEARCH_URL = "https://pixabay.com/api/videos/"
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"
MIN_VIDEO_WIDTH = 720


def is_stock_video_enabled() -> bool:
    settings = get_settings()
    return bool(settings.pexels_api_key.strip() or settings.pixabay_api_key.strip())


def fetch_scene_stock_video(
    visual_plan: SceneVisualPlan,
    scene_index: int,
    width: int,
    height: int,
) -> Path | None:
    """Download a stock clip for one scene."""
    if not is_stock_video_enabled():
        return None

    settings = get_settings()
    orientation = "landscape" if width >= height else "portrait"
    queries = list(visual_plan.search_keywords) or [visual_plan.image_search_prompt]
    primary_query = queries[0]
    cache_dir = settings.cache_dir / "stock_videos" / orientation
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.md5(
        f"{orientation}|{primary_query}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:20]
    target_path = cache_dir / f"{cache_key}.mp4"
    if target_path.exists() and target_path.stat().st_size > 50_000:
        logger.info("Stock video cache hit scene %d — %s", scene_index + 1, primary_query)
        return target_path

    provider = _resolve_stock_video_provider(settings)
    if provider == "pexels" and settings.pexels_api_key.strip():
        clip_path = _fetch_from_pexels(
            queries,
            scene_index,
            visual_plan.image_search_prompt,
            orientation,
            target_path,
            settings.pexels_api_key.strip(),
        )
        if clip_path is not None:
            return clip_path

    if settings.pixabay_api_key.strip():
        clip_path = _fetch_from_pixabay(
            queries,
            scene_index,
            visual_plan.image_search_prompt,
            visual_plan.visual_style,
            orientation,
            target_path,
            settings.pixabay_api_key.strip(),
        )
        if clip_path is not None:
            return clip_path

    if provider != "pexels" and settings.pexels_api_key.strip():
        return _fetch_from_pexels(
            queries,
            scene_index,
            visual_plan.image_search_prompt,
            orientation,
            target_path,
            settings.pexels_api_key.strip(),
        )
    return None


def attach_stock_videos_to_scenes(
    scenes: list,
    visual_plans: list[SceneVisualPlan],
    width: int,
    height: int,
) -> list:
    """Return scenes with stock_video_path populated when downloads succeed."""
    from futuredecoded.media.scene_planner import VideoScene

    if not visual_plans:
        return scenes

    updated_scenes: list[VideoScene] = []
    for index, scene in enumerate(scenes):
        plan = visual_plans[index % len(visual_plans)]
        stock_video_path = fetch_scene_stock_video(plan, index, width, height)
        updated_scenes.append(
            VideoScene(
                section_label=scene.section_label,
                duration_seconds=scene.duration_seconds,
                visual_query=scene.visual_query,
                image_path=scene.image_path,
                animation_type=scene.animation_type,
                text_overlay=scene.text_overlay,
                is_hook_scene=scene.is_hook_scene,
                scene_description=scene.scene_description,
                image_search_prompt=plan.image_search_prompt,
                search_keywords=plan.search_keywords,
                visual_style=plan.visual_style,
                stock_video_path=stock_video_path,
            )
        )
    return updated_scenes


def _resolve_stock_video_provider(settings) -> str:
    configured = getattr(settings, "stock_video_provider", "pexels").strip().lower()
    if configured in {"pexels", "pixabay"}:
        return configured
    return "pexels"


def _fetch_from_pexels(
    queries: list[str],
    scene_index: int,
    image_search_prompt: str,
    orientation: str,
    target_path: Path,
    api_key: str,
) -> Path | None:
    for query_index, query in enumerate(queries):
        video_url = _search_pexels_video_url(
            query=query,
            api_key=api_key,
            orientation=orientation,
            image_search_prompt=image_search_prompt,
            result_index=query_index,
        )
        if video_url and _download_video(video_url, target_path):
            logger.info("Pexels clip scene %d — %s", scene_index + 1, query)
            return target_path
    return None


def _fetch_from_pixabay(
    queries: list[str],
    scene_index: int,
    image_search_prompt: str,
    visual_style: str,
    orientation: str,
    target_path: Path,
    api_key: str,
) -> Path | None:
    video_type = "animation" if visual_style == VisualStyle.MOTION_GRAPHICS.value else "film"
    for query_index, query in enumerate(queries):
        video_url = _search_pixabay_video_url(
            query=query,
            api_key=api_key,
            video_type=video_type,
            orientation=orientation,
            image_search_prompt=image_search_prompt,
            result_index=query_index,
        )
        if video_url and _download_video(video_url, target_path):
            logger.info("Pixabay clip scene %d — %s", scene_index + 1, query)
            return target_path
    return None


def _search_pexels_video_url(
    query: str,
    api_key: str,
    orientation: str,
    image_search_prompt: str,
    result_index: int,
) -> str | None:
    params = urllib.parse.urlencode(
        {
            "query": query[:100],
            "per_page": "15",
            "orientation": orientation,
            "size": "medium",
        }
    )
    request = urllib.request.Request(
        f"{PEXELS_VIDEO_SEARCH_URL}?{params}",
        headers={"Authorization": api_key, "User-Agent": "FutureDecodedBot/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Pexels search failed (%s): %s", query, exc)
        return None

    videos = payload.get("videos", [])
    if not videos:
        return None

    relevance_text = image_search_prompt.strip() or query
    if relevance_text and len(videos) > 1:
        ranked = sorted(
            videos,
            key=lambda video: score_video_tag_relevance(
                relevance_text,
                str(video.get("url", "")) + " " + " ".join(video.get("tags", []) or []),
            ),
            reverse=True,
        )
        chosen = ranked[result_index % len(ranked)]
    else:
        chosen = videos[result_index % len(videos)]
    return _pick_pexels_video_url(chosen.get("video_files", []))


def _search_pixabay_video_url(
    query: str,
    api_key: str,
    video_type: str,
    orientation: str,
    image_search_prompt: str,
    result_index: int,
) -> str | None:
    params = urllib.parse.urlencode(
        {
            "key": api_key,
            "q": query[:100],
            "video_type": video_type,
            "orientation": orientation,
            "per_page": "20",
            "min_width": str(MIN_VIDEO_WIDTH),
            "safesearch": "true",
        }
    )
    request = urllib.request.Request(
        f"{PIXABAY_VIDEO_SEARCH_URL}?{params}",
        headers={"User-Agent": "FutureDecodedBot/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Pixabay search failed (%s): %s", query, exc)
        return None

    hits = payload.get("hits", [])
    if not hits:
        return None

    relevance_text = image_search_prompt.strip() or query
    if relevance_text and len(hits) > 1:
        ranked = sorted(
            hits,
            key=lambda hit: score_video_tag_relevance(relevance_text, str(hit.get("tags", ""))),
            reverse=True,
        )
        chosen = ranked[result_index % len(ranked)]
    else:
        chosen = hits[result_index % len(hits)]
    return _pick_pixabay_video_url(chosen.get("videos", {}))


def _pick_pexels_video_url(video_files: list[dict]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for file_info in video_files:
        link = file_info.get("link")
        width = int(file_info.get("width") or 0)
        if link and width >= MIN_VIDEO_WIDTH:
            candidates.append((width, link))

    if not candidates:
        for file_info in video_files:
            link = file_info.get("link")
            if link:
                return link
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[len(candidates) // 2][1]


def _pick_pixabay_video_url(videos: dict) -> str | None:
    for size_key in ("large", "medium", "small", "tiny"):
        rendition = videos.get(size_key, {})
        url = rendition.get("url")
        width = int(rendition.get("width") or 0)
        if url and width >= MIN_VIDEO_WIDTH:
            return url

    for size_key in ("large", "medium", "small", "tiny"):
        rendition = videos.get(size_key, {})
        url = rendition.get("url")
        if url:
            return url
    return None


def _download_video(url: str, target_path: Path) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "FutureDecodedBot/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        if len(data) < 50_000:
            return False
        target_path.write_bytes(data)
        return True
    except Exception as exc:
        logger.warning("Stock video download failed: %s", exc)
        return False


def probe_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return max(float(result.stdout.strip()), 0.1)
    except ValueError:
        return 0.0


def validate_stock_video_clip(video_path: Path, minimum_bytes: int = 50_000) -> bool:
    """Return True when a downloaded stock clip is present and decodable."""
    if not video_path.exists():
        return False
    if video_path.stat().st_size < minimum_bytes:
        return False
    return probe_video_duration(video_path) > 0.0
