"""YouTube monetization and quality compliance checks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("futuredecoded.editorial.compliance")

MIN_LONG_SCRIPT_WORDS = 400

REQUIRED_SECTION_LABELS = (
    "hook",
    "background",
    "problem",
    "context",
    "news",
    "matters",
    "impact",
    "future",
    "outlook",
    "wrap",
)

FILLER_PHRASES = (
    "in today's video",
    "without further ado",
    "smash that like button",
    "don't forget to subscribe",
    "hello guys",
    "hey guys",
)

CLICKBAIT_WITHOUT_EVIDENCE = (
    "you won't believe",
    "shocking truth",
    "they don't want you to know",
)


@dataclass
class ComplianceResult:
    passed: bool
    issues: list[str]
    word_count: int


def validate_script_compliance(
    script_long: str,
    script_sections: list[dict[str, str]],
    story_title: str,
) -> ComplianceResult:
    issues: list[str] = []
    word_count = len(script_long.split())

    if word_count < MIN_LONG_SCRIPT_WORDS:
        issues.append(
            f"Script too short for monetization-safe analysis ({word_count} words, min {MIN_LONG_SCRIPT_WORDS})"
        )

    if word_count > 950:
        issues.append(f"Script too long ({word_count} words, target 600-900)")

    section_text = " ".join(str(section.get("label", "")).lower() for section in script_sections)
    if not any(label in section_text for label in REQUIRED_SECTION_LABELS[:3]):
        issues.append("Missing hook/context section structure")

    lowered_script = script_long.lower()
    for phrase in FILLER_PHRASES:
        if phrase in lowered_script:
            issues.append(f"Generic filler detected: '{phrase}'")

    for phrase in CLICKBAIT_WITHOUT_EVIDENCE:
        if phrase in story_title.lower() or phrase in lowered_script:
            issues.append(f"Clickbait phrase without evidence: '{phrase}'")

    if _has_excessive_repetition(script_long):
        issues.append("Script contains excessive phrase repetition")

    passed = len(issues) == 0
    if not passed:
        logger.warning("Compliance issues: %s", "; ".join(issues[:3]))
    return ComplianceResult(passed=passed, issues=issues, word_count=word_count)


def _has_excessive_repetition(script_text: str, min_phrase_words: int = 4) -> bool:
    words = re.findall(r"[a-z0-9']+", script_text.lower())
    if len(words) < 40:
        return False
    for index in range(len(words) - min_phrase_words):
        phrase = " ".join(words[index : index + min_phrase_words])
        if script_text.lower().count(phrase) >= 3:
            return True
    return False
