"""Tests for scene planner."""

from pathlib import Path

from futuredecoded.media.scene_planner import (
    HOOK_SCENE_DURATION_SECONDS,
    MAX_SCENE_DURATION_SECONDS,
    plan_video_scenes,
)


def test_plan_video_scenes_uses_hook_fast_cuts(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    sections = [{"label": "Hook", "text": "OpenAI just launched GPT-5"}]
    images = [Path("img1.jpg"), Path("img2.jpg"), Path("img3.jpg")]
    scenes = plan_video_scenes(sections, total_duration_seconds=20.0, story_title="OpenAI GPT-5", image_paths=images)

    assert len(scenes) >= 5
    assert scenes[0].duration_seconds <= HOOK_SCENE_DURATION_SECONDS + 0.01
    assert scenes[0].is_hook_scene is True
    assert all(scene.duration_seconds <= MAX_SCENE_DURATION_SECONDS + 0.01 for scene in scenes)


def test_plan_video_scenes_avoids_consecutive_duplicate_images(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    sections = [{"label": "Hook", "text": "Intro"}]
    images = [Path("a.jpg"), Path("b.jpg")]
    scenes = plan_video_scenes(sections, total_duration_seconds=12.0, story_title="Story", image_paths=images)

    for index in range(len(scenes) - 1):
        if scenes[index].image_path and scenes[index + 1].image_path:
            if len(images) > 1:
                assert scenes[index].image_path != scenes[index + 1].image_path


def test_plan_video_scenes_assigns_motion_and_overlay(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    sections = [{"label": "Hook", "text": "Anthropic announces safety update"}]
    images = [Path("a.jpg")]
    scenes = plan_video_scenes(sections, total_duration_seconds=9.0, story_title="Anthropic Safety", image_paths=images)

    assert scenes[0].animation_type in {"zoom_in", "zoom_out", "pan_left", "pan_right"}
    assert scenes[0].text_overlay is not None


def test_plan_video_scenes_even_merge_avoids_giant_first_scene(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("USE_CINEMATIC_RENDERER", "true")
    sections = [{"label": "Hook", "text": "OpenAI launches GPT-5"}]
    images = [Path("a.jpg")]
    scenes = plan_video_scenes(
        sections,
        total_duration_seconds=215.0,
        story_title="OpenAI GPT-5",
        image_paths=images,
    )

    assert len(scenes) > 12
    assert max(scene.duration_seconds for scene in scenes) <= 5.5
    assert abs(sum(scene.duration_seconds for scene in scenes) - 215.0) < 1.0
