"""YouTube publish schedule planner — IST publish slots."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

LONG_FORM_PUBLISH_HOUR_IST = 8
LONG_FORM_PUBLISH_MINUTE_IST = 0
SHORTS_PUBLISH_HOUR_IST = 18
SHORTS_PUBLISH_MINUTE_IST = 30


def resolve_next_publish_time_utc(
    hour_ist: int,
    minute_ist: int,
    reference_time: datetime | None = None,
) -> datetime:
    """Return the next publish instant in UTC for a daily IST slot."""
    now_ist = (reference_time or datetime.now(UTC)).astimezone(IST)
    candidate_ist = now_ist.replace(hour=hour_ist, minute=minute_ist, second=0, microsecond=0)
    if candidate_ist <= now_ist:
        candidate_ist += timedelta(days=1)
    return candidate_ist.astimezone(UTC)


def resolve_long_form_publish_time_utc(reference_time: datetime | None = None) -> datetime:
    return resolve_next_publish_time_utc(
        LONG_FORM_PUBLISH_HOUR_IST,
        LONG_FORM_PUBLISH_MINUTE_IST,
        reference_time,
    )


def resolve_shorts_publish_time_utc(reference_time: datetime | None = None) -> datetime:
    return resolve_next_publish_time_utc(
        SHORTS_PUBLISH_HOUR_IST,
        SHORTS_PUBLISH_MINUTE_IST,
        reference_time,
    )


def format_publish_at_for_youtube(publish_time_utc: datetime) -> str:
    normalized = publish_time_utc.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")
