"""Social distribution — X, LinkedIn, Telegram."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from futuredecoded.config.settings import get_settings

logger = logging.getLogger("futuredecoded.publish.social")


def publish_social_posts(seo_social: dict, video_url: str, output_dir: Path) -> dict[str, bool]:
    settings = get_settings()
    results: dict[str, bool] = {}

    posts = {
        "x": seo_social.get("x", "").replace("LINK", video_url),
        "linkedin": seo_social.get("linkedin", "").replace("LINK", video_url),
        "telegram": seo_social.get("telegram", "").replace("LINK", video_url),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "social_posts.json").write_text(json.dumps(posts, indent=2), encoding="utf-8")

    if settings.dry_run:
        logger.info("[DRY RUN] Social posts saved to social_posts.json")
        return {"x": True, "linkedin": True, "telegram": True}

    if settings.x_bearer_token and posts.get("x"):
        results["x"] = _publish_x(posts["x"], settings.x_bearer_token)
    if settings.telegram_bot_token and settings.telegram_channel_id and posts.get("telegram"):
        results["telegram"] = _publish_telegram(
            posts["telegram"], settings.telegram_bot_token, settings.telegram_channel_id
        )
    results["linkedin"] = False  # Requires manual or partner API
    logger.info("Social publish results: %s", results)
    return results


def _publish_x(text: str, bearer_token: str) -> bool:
    try:
        resp = requests.post(
            "https://api.twitter.com/2/tweets",
            headers={"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"},
            json={"text": text[:280]},
            timeout=15,
        )
        return resp.status_code in (200, 201)
    except Exception as exc:
        logger.warning("X publish failed: %s", exc)
        return False


def _publish_telegram(text: str, bot_token: str, channel_id: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": channel_id, "text": text[:4096]},
            timeout=15,
        )
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("Telegram publish failed: %s", exc)
        return False
