"""Tests for visual style classification."""

from futuredecoded.config.visual_style import VisualStyle, classify_section_visual_style


def test_classify_section_visual_style_uses_motion_graphics_for_hook():
    style = classify_section_visual_style("Hook", "OpenAI launches a new model today")
    assert style == VisualStyle.MOTION_GRAPHICS


def test_classify_section_visual_style_uses_real_footage_for_background():
    style = classify_section_visual_style("Background", "Executives met in Washington last week")
    assert style == VisualStyle.REAL_FOOTAGE
