"""Tests for scene planner."""

from pathlib import Path

from futuredecoded.media.scene_planner import SCENE_DURATION_SECONDS, plan_video_scenes


def test_plan_video_scenes_targets_four_second_cuts():
    sections = [
        {"label": "Hook", "text": "Big news today"},
        {"label": "Impact", "text": "Why it matters"},
    ]
    images = [Path("img1.jpg"), Path("img2.jpg")]
    scenes = plan_video_scenes(sections, total_duration_seconds=20.0, story_title="AI launch", image_paths=images)

    assert len(scenes) == 5
    assert scenes[0].duration_seconds == SCENE_DURATION_SECONDS
    assert scenes[-1].duration_seconds >= SCENE_DURATION_SECONDS


def test_plan_video_scenes_assigns_images_round_robin():
    sections = [{"label": "Hook", "text": "Intro"}]
    images = [Path("a.jpg"), Path("b.jpg")]
    scenes = plan_video_scenes(sections, total_duration_seconds=12.0, story_title="Story", image_paths=images)

    assert scenes[0].image_path == Path("a.jpg")
    assert scenes[1].image_path == Path("b.jpg")
