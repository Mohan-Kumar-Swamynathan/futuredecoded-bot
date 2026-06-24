"""Tests for stock video collector."""

from pathlib import Path

import futuredecoded.media.stock_video_collector as stock_video_collector
from futuredecoded.media.scene_visual_planner import SceneVisualPlan


def test_is_stock_video_enabled_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        stock_video_collector,
        "get_settings",
        lambda: type("Settings", (), {"pexels_api_key": "", "pixabay_api_key": ""})(),
    )
    assert stock_video_collector.is_stock_video_enabled() is False


def test_attach_stock_videos_to_scenes_preserves_duration(monkeypatch, tmp_path):
    from futuredecoded.media.scene_planner import VideoScene

    monkeypatch.setattr(stock_video_collector, "fetch_scene_stock_video", lambda *args, **kwargs: None)
    scenes = [
        VideoScene(
            section_label="Hook",
            duration_seconds=3.5,
            visual_query="hook",
            image_path=Path("image.jpg"),
        )
    ]
    plans = [
        SceneVisualPlan(
            section_label="Hook",
            section_text="OpenAI launches GPT-5",
            image_search_prompt="OpenAI GPT launch technology",
            search_keywords=("OpenAI GPT launch",),
            visual_style="motion_graphics",
        )
    ]
    updated = stock_video_collector.attach_stock_videos_to_scenes(scenes, plans, 1920, 1080)
    assert updated[0].duration_seconds == 3.5
    assert updated[0].image_search_prompt == "OpenAI GPT launch technology"
    assert updated[0].stock_video_path is None
