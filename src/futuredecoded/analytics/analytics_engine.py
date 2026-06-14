"""Analytics engine — track YouTube metrics."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from futuredecoded.database.models import AnalyticsRecord, get_session

logger = logging.getLogger("futuredecoded.analytics.engine")


def store_analytics_snapshot(video_id: str, metrics: dict) -> None:
    session = get_session()
    try:
        record = AnalyticsRecord(
            video_id=video_id,
            views=metrics.get("views", 0),
            watch_time_minutes=metrics.get("watch_time_minutes", 0.0),
            ctr=metrics.get("ctr", 0.0),
            retention=metrics.get("retention", 0.0),
            subscribers_gained=metrics.get("subscribers_gained", 0),
            recorded_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()
        logger.info("Analytics stored for video %s", video_id)
    finally:
        session.close()


def generate_weekly_report(output_path: Path) -> None:
    session = get_session()
    try:
        records = session.query(AnalyticsRecord).order_by(AnalyticsRecord.recorded_at.desc()).limit(50).all()
    finally:
        session.close()

    html = _build_report_html("Weekly Analytics Report", records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Weekly report: %s", output_path)


def generate_monthly_report(output_path: Path) -> None:
    generate_weekly_report(output_path.with_name("monthly_report.html"))


def _build_report_html(title: str, records: list) -> str:
    rows = "".join(
        f"<tr><td>{record.video_id}</td><td>{record.views}</td>"
        f"<td>{record.ctr:.1f}%</td><td>{record.retention:.1f}%</td></tr>"
        for record in records
    )
    return f"""<!DOCTYPE html>
<html><head><title>{title}</title>
<style>body{{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #334155;padding:8px}}</style>
</head><body><h1>{title}</h1><p>FutureDecoded — Making Sense of Tomorrow</p>
<table><tr><th>Video</th><th>Views</th><th>CTR</th><th>Retention</th></tr>{rows}</table>
</body></html>"""
