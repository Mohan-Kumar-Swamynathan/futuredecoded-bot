"""Visual collector — Pexels, Pixabay, Unsplash fallback."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

from futuredecoded.config.settings import get_settings

logger = logging.getLogger("futuredecoded.media.visuals")


def collect_visuals(topic_slug: str, keywords: list[str], max_images: int = 8) -> list[Path]:
    settings = get_settings()
    asset_dir = settings.assets_dir / topic_slug
    asset_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    if settings.pexels_api_key:
        downloaded.extend(_fetch_pexels(keywords, asset_dir, max_images, settings.pexels_api_key))
    if len(downloaded) < 3 and settings.pixabay_api_key:
        downloaded.extend(_fetch_pixabay(keywords, asset_dir, max_images - len(downloaded), settings.pixabay_api_key))

    if len(downloaded) < 3:
        downloaded.extend(
            _generate_placeholder_images(asset_dir, max(3, max_images - len(downloaded)))
        )

    logger.info("Collected %d visuals for %s", len(downloaded), topic_slug)
    return downloaded[:max_images]


def _fetch_pexels(keywords: list[str], dest: Path, limit: int, api_key: str) -> list[Path]:
    images: list[Path] = []
    headers = {"Authorization": api_key}
    for keyword in keywords:
        if len(images) >= limit:
            break
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": keyword, "per_page": 5, "orientation": "landscape"},
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            for photo in resp.json().get("photos", []):
                src = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
                if not src:
                    continue
                file_hash = hashlib.md5(src.encode()).hexdigest()[:8]
                path = dest / f"pexels_{file_hash}.jpg"
                if path.exists():
                    images.append(path)
                    continue
                image_resp = requests.get(src, timeout=20)
                if image_resp.status_code == 200:
                    path.write_bytes(image_resp.content)
                    images.append(path)
                if len(images) >= limit:
                    break
        except Exception as exc:
            logger.debug("Pexels error: %s", exc)
    return images


def _fetch_pixabay(keywords: list[str], dest: Path, limit: int, api_key: str) -> list[Path]:
    images: list[Path] = []
    for keyword in keywords[:2]:
        if len(images) >= limit:
            break
        try:
            resp = requests.get(
                "https://pixabay.com/api/",
                params={"key": api_key, "q": keyword, "image_type": "photo", "per_page": 5},
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            for hit in resp.json().get("hits", []):
                url = hit.get("largeImageURL")
                if not url:
                    continue
                file_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                path = dest / f"pixabay_{file_hash}.jpg"
                image_resp = requests.get(url, timeout=20)
                if image_resp.status_code == 200:
                    path.write_bytes(image_resp.content)
                    images.append(path)
                if len(images) >= limit:
                    break
        except Exception as exc:
            logger.debug("Pixabay error: %s", exc)
    return images


def _generate_placeholder_images(dest: Path, count: int) -> list[Path]:
    from PIL import Image, ImageDraw
    paths: list[Path] = []
    colors = [(20, 30, 60), (30, 20, 50), (10, 40, 70)]
    for index in range(count):
        path = dest / f"placeholder_{index}.png"
        img = Image.new("RGB", (1920, 1080), colors[index % len(colors)])
        draw = ImageDraw.Draw(img)
        draw.text((100, 500), "FutureDecoded", fill=(255, 255, 255))
        img.save(path)
        paths.append(path)
    return paths
