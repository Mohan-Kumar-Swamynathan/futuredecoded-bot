"""Tests for compliance guard."""

from futuredecoded.editorial.compliance_guard import validate_script_compliance


def test_validate_script_compliance_passes_for_journalist_structure():
    sections = [
        {"label": "Hook", "text": "OpenAI just changed the game."},
        {"label": "Problem", "text": "Developers need better agents."},
        {"label": "Impact", "text": "This affects every AI startup."},
    ]
    script = " ".join(f"word{i}" for i in range(450))

    result = validate_script_compliance(script, sections, "OpenAI launches new agent builder")

    assert result.passed is True
    assert result.word_count >= 400


def test_validate_script_compliance_rejects_filler_phrases():
    sections = [{"label": "Hook", "text": "Intro"}]
    script = ("In today's video we discuss AI. " + "word " * 420).strip()

    result = validate_script_compliance(script, sections, "AI update")

    assert result.passed is False
    assert any("filler" in issue.lower() for issue in result.issues)
