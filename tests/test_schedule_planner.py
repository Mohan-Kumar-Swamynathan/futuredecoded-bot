"""Tests for publish schedule planner."""

from datetime import datetime
from zoneinfo import ZoneInfo

from futuredecoded.publish.schedule_planner import (
    format_publish_at_for_youtube,
    resolve_long_form_publish_time_utc,
    resolve_shorts_publish_time_utc,
)

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def test_long_form_publish_defaults_to_next_8am_ist():
    reference = datetime(2026, 6, 15, 7, 0, tzinfo=IST)
    publish_time = resolve_long_form_publish_time_utc(reference)
    publish_ist = publish_time.astimezone(IST)
    assert publish_ist.hour == 8
    assert publish_ist.minute == 0


def test_shorts_publish_defaults_to_same_day_630pm_ist():
    reference = datetime(2026, 6, 15, 8, 30, tzinfo=IST)
    publish_time = resolve_shorts_publish_time_utc(reference)
    publish_ist = publish_time.astimezone(IST)
    assert publish_ist.hour == 18
    assert publish_ist.minute == 30
    assert publish_ist.day == 15


def test_shorts_publish_rolls_to_next_day_after_slot():
    reference = datetime(2026, 6, 15, 19, 0, tzinfo=IST)
    publish_time = resolve_shorts_publish_time_utc(reference)
    publish_ist = publish_time.astimezone(IST)
    assert publish_ist.day == 16
    assert publish_ist.hour == 18
    assert publish_ist.minute == 30


def test_format_publish_at_for_youtube_uses_z_suffix():
    publish_time = datetime(2026, 6, 15, 2, 30, tzinfo=UTC)
    assert format_publish_at_for_youtube(publish_time) == "2026-06-15T02:30:00Z"
