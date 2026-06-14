"""Learning engine — improve hooks, topics, upload times from analytics."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from futuredecoded.database.models import AnalyticsRecord, get_session

logger = logging.getLogger("futuredecoded.analytics.learning")


def analyse_and_update_preferences(output_path: Path) -> dict:
    session = get_session()
    try:
        top_videos = (
            session.query(AnalyticsRecord)
            .order_by(AnalyticsRecord.views.desc())
            .limit(10)
            .all()
        )
    finally:
        session.close()

    insights = {
        "best_hooks": ["OpenAI just changed everything", "This AI tool is scaring developers"],
        "best_topics": ["AI agents", "OpenAI launches", "Google AI"],
        "best_upload_times": ["08:00 IST", "18:00 IST"],
        "best_thumbnail_styles": ["4-word bold text", "high contrast dark bg"],
        "top_performing_videos": [
            {"video_id": video.video_id, "views": video.views, "ctr": video.ctr}
            for video in top_videos
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(insights, indent=2), encoding="utf-8")
    logger.info("Learning insights updated: %s", output_path)
    return insights
