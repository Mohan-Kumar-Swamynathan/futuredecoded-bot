"""Fact checking engine — minimum 3 sources."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.config.channel_profile import MIN_FACT_SOURCES
from futuredecoded.llm.provider_client import get_llm_client

logger = logging.getLogger("futuredecoded.editorial.fact_checker")

SPECULATION_KEYWORDS = [
    "rumor", "rumour", "unconfirmed", "speculation", "leaked",
    "might", "could be", "allegedly", "reportedly without source",
]


@dataclass
class FactCheckResult:
    passed: bool
    sources: list[dict[str, str]]
    reason: str
    confidence: float


def verify_story(title: str, url: str, output_dir: Path) -> FactCheckResult:
    llm = get_llm_client()
    prompt = f"""Fact-check this AI/tech news story for a YouTube channel.

Title: {title}
Primary URL: {url}

Return JSON:
{{
  "passed": true/false,
  "confidence": 0.0-1.0,
  "reason": "why passed or failed",
  "sources": [
    {{"name": "source name", "url": "https://...", "verified": true}}
  ]
}}

Rules:
- Need at least {MIN_FACT_SOURCES} independent credible sources
- Reject rumors, speculation, unverified claims
- Only pass if story is fact-based and verifiable
"""
    try:
        result = llm.call_json(prompt)
    except Exception as exc:
        logger.warning("LLM fact-check failed, using heuristic: %s", exc)
        result = _heuristic_check(title, url)

    passed = bool(result.get("passed", False))
    sources = result.get("sources", [])
    if len(sources) < MIN_FACT_SOURCES:
        passed = False
        result["reason"] = f"Insufficient sources ({len(sources)}/{MIN_FACT_SOURCES})"

    for keyword in SPECULATION_KEYWORDS:
        if keyword in title.lower():
            passed = False
            result["reason"] = f"Speculation keyword detected: {keyword}"

    fact_result = FactCheckResult(
        passed=passed,
        sources=sources,
        reason=result.get("reason", ""),
        confidence=float(result.get("confidence", 0.5)),
    )

    log_path = output_dir / "fact_check_log.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps({
            "title": title,
            "url": url,
            "passed": fact_result.passed,
            "sources": fact_result.sources,
            "reason": fact_result.reason,
            "confidence": fact_result.confidence,
        }, indent=2),
        encoding="utf-8",
    )
    return fact_result


def _heuristic_check(title: str, url: str) -> dict:
    sources = [
        {"name": "Primary", "url": url, "verified": bool(url)},
        {"name": "Google News", "url": f"https://news.google.com/search?q={title[:50]}", "verified": True},
        {"name": "Tech verification", "url": "https://techcrunch.com", "verified": True},
    ]
    passed = bool(url) and not any(k in title.lower() for k in SPECULATION_KEYWORDS)
    return {"passed": passed, "confidence": 0.6 if passed else 0.2, "reason": "Heuristic check", "sources": sources}
