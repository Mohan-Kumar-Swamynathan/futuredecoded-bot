"""Tests for per-scene visual planning."""

from futuredecoded.media.scene_visual_planner import build_scene_visual_plans, enrich_sections_with_visual_metadata


def test_build_scene_visual_plans_adds_keywords_and_prompt():
    sections = [
        {"label": "Hook", "text": "Anthropic releases Claude safety update"},
        {"label": "Background", "text": "Regulators reviewed enterprise AI deployments"},
    ]
    plans = build_scene_visual_plans(sections, "Anthropic Claude Safety Update")

    assert len(plans) == 2
    assert plans[0].image_search_prompt
    assert len(plans[0].search_keywords) >= 1
    assert plans[0].visual_style in {"real_footage", "motion_graphics"}


def test_enrich_sections_with_visual_metadata_preserves_text():
    sections = [{"label": "Hook", "text": "NVIDIA unveils new AI chip"}]
    enriched = enrich_sections_with_visual_metadata(sections, "NVIDIA AI Chip")

    assert enriched[0]["text"] == sections[0]["text"]
    assert enriched[0]["image_search_prompt"]
    assert enriched[0]["search_keywords"]
    assert enriched[0]["visual_style"]
