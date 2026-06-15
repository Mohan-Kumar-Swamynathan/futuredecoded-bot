"""Visual keyword builder — story-relevant search queries."""

from __future__ import annotations

import re

STOP_WORDS = frozenset({
    "about", "after", "also", "amid", "amidst", "among", "been", "from", "into",
    "just", "more", "news", "over", "says", "said", "that", "the", "their", "this",
    "triggered", "under", "what", "when", "with", "will", "amid", "amidst",
})


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-']*", text)
    return [token for token in tokens if len(token) > 2 and token.lower() not in STOP_WORDS]


def build_visual_search_queries(
    story_title: str,
    outline: dict | None = None,
    sections: list[dict[str, str]] | None = None,
) -> list[str]:
    outline = outline or {}
    sections = sections or []
    title_tokens = _tokenize(story_title)

    queries: list[str] = []
    if len(title_tokens) >= 2:
        queries.append(" ".join(title_tokens[:5]))
    if len(title_tokens) >= 3:
        queries.append(" ".join(title_tokens[:3]))

    for fact in outline.get("key_facts", [])[:3]:
        fact_tokens = _tokenize(str(fact))
        if len(fact_tokens) >= 2:
            queries.append(" ".join(fact_tokens[:4]))

    for section in sections[:4]:
        section_label = str(section.get("label", "")).strip()
        section_text = str(section.get("text", "")).strip()
        section_tokens = _tokenize(f"{section_label} {section_text}")
        if len(section_tokens) >= 2:
            queries.append(" ".join(section_tokens[:4]))

    entity_queries = _build_entity_queries(title_tokens)
    queries.extend(entity_queries)

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = " ".join(query.lower().split())
        if normalized and normalized not in seen:
            deduped.append(query.strip())
            seen.add(normalized)

    if not deduped:
        deduped = ["artificial intelligence technology", "business technology news"]
    return deduped[:10]


def _build_entity_queries(title_tokens: list[str]) -> list[str]:
    queries: list[str] = []
    joined = " ".join(title_tokens).lower()

    entity_visuals = {
        "openai": ["ChatGPT interface", "AI neural network", "developer coding AI"],
        "anthropic": ["AI safety research lab", "artificial intelligence server room", "AI ethics technology"],
        "google": ["Google Gemini AI", "Android technology", "data center cloud computing"],
        "gemini": ["Google Gemini AI interface", "AI assistant technology"],
        "gpt": ["ChatGPT interface", "AI language model visualization"],
        "claude": ["AI assistant interface", "enterprise AI software"],
        "tesla": ["Tesla electric vehicle", "Tesla factory automation", "EV charging station"],
        "nvidia": ["NVIDIA GPU data center", "AI chip technology", "machine learning hardware"],
        "robot": ["humanoid robot technology", "factory automation robot arm"],
        "robotics": ["robotics laboratory", "autonomous robot warehouse"],
        "amazon": ["Amazon corporate technology", "cloud computing data center"],
        "meta": ["virtual reality headset technology", "metaverse digital network"],
        "microsoft": ["cloud computing server room", "enterprise software developer"],
        "startup": ["technology startup office", "innovation brainstorming team"],
        "ev": ["electric vehicle charging", "battery factory technology"],
        "chip": ["semiconductor fabrication", "computer chip macro"],
        "regulation": ["government technology policy meeting", "capitol building technology"],
    }

    for keyword, visuals in entity_visuals.items():
        if keyword in joined:
            queries.extend(visuals[:2])

    if "ceo" in joined:
        queries.append("CEO technology keynote presentation")
    if "launch" in joined or "release" in joined:
        queries.append("product launch technology event")

    return queries


def score_image_relevance(story_title: str, alt_text: str, query: str) -> float:
    story_tokens = set(_tokenize(story_title))
    alt_tokens = set(_tokenize(alt_text))
    query_tokens = set(_tokenize(query))
    combined_tokens = alt_tokens | query_tokens

    if not story_tokens:
        return 0.0

    overlap = len(story_tokens & combined_tokens)
    score = overlap / len(story_tokens)
    if "generic" in alt_text.lower() or "business handshake" in alt_text.lower():
        score -= 0.4
    if "unrelated" in alt_text.lower():
        score -= 0.5

    return max(0.0, min(1.0, score))
