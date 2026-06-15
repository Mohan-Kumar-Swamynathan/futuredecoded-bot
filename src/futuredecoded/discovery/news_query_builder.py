"""Normalize story titles into effective news search queries."""

from __future__ import annotations

import re

_TITLE_PREFIX_PATTERN = re.compile(
    r"^(?:trending|show hn|launch hn|breaking|update|news)\s*:\s*",
    flags=re.IGNORECASE,
)
_REPO_PATH_PATTERN = re.compile(r"\b[a-z0-9_-]+/[a-z0-9._-]+\b", flags=re.IGNORECASE)


def normalize_story_title_for_search(title: str) -> str:
    cleaned = _TITLE_PREFIX_PATTERN.sub("", title.strip())
    if "—" in cleaned:
        cleaned = cleaned.split("—", maxsplit=1)[-1].strip()
    if " - " in cleaned:
        parts = cleaned.split(" - ")
        if len(parts[-1]) > 20:
            cleaned = parts[-1].strip()
    cleaned = _REPO_PATH_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_news_search_queries(title: str, limit: int = 4) -> list[str]:
    normalized = normalize_story_title_for_search(title)
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-']*", normalized)
        if len(token) > 2 and token.lower() not in {"the", "and", "for", "with", "from"}
    ]

    queries: list[str] = []
    if normalized:
        queries.append(normalized[:100])
    if len(tokens) >= 3:
        queries.append(" ".join(tokens[:5]))
    if len(tokens) >= 2:
        queries.append(" ".join(tokens[:3]))

    topic_hint = " ".join(token for token in tokens if token.lower() in {
        "ai", "openai", "google", "anthropic", "tesla", "nvidia", "amazon", "robotics", "startup",
    })
    if topic_hint:
        queries.append(f"{topic_hint} technology news")

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower().strip()
        if key and key not in seen:
            deduped.append(query.strip())
            seen.add(key)
        if len(deduped) >= limit:
            break
    return deduped or [title[:80]]
