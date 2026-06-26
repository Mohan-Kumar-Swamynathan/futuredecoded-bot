"""Visual keyword builder — story-relevant search queries."""

from __future__ import annotations

import re

from futuredecoded.config.visual_style import VisualStyle, style_query_suffix

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
    token_set = {token.lower() for token in title_tokens}
    joined = " ".join(title_tokens).lower()
    normalized_joined = joined.replace("-", "")

    entity_visuals = {
        "gptzero": [
            "AI content detection software",
            "plagiarism detection technology screen",
            "AI writing analysis dashboard",
        ],
        "superhuman": [
            "email productivity software",
            "business professional laptop workflow",
            "startup office technology team",
        ],
        "openai": ["ChatGPT interface", "AI neural network", "developer coding AI"],
        "anthropic": ["AI safety research lab", "artificial intelligence server room", "AI ethics technology"],
        "alibaba": ["Alibaba corporate technology office", "ecommerce technology business"],
        "google": ["Google Gemini AI", "Android technology", "data center cloud computing"],
        "gemini": ["Google Gemini AI interface", "AI assistant technology"],
        "claude": ["AI assistant interface", "enterprise AI software"],
        "tesla": ["Tesla electric vehicle", "Tesla factory automation", "EV charging station"],
        "nvidia": ["NVIDIA GPU data center", "AI chip technology", "machine learning hardware"],
        "robot": ["humanoid robot technology", "factory automation robot arm"],
        "robotics": ["robotics laboratory", "autonomous robot warehouse"],
        "amazon": ["Amazon corporate technology", "cloud computing data center"],
        "meta": ["virtual reality headset technology", "metaverse digital network"],
        "microsoft": ["cloud computing server room", "enterprise software developer"],
        "startup": ["technology startup office", "innovation brainstorming team"],
        "acquires": ["business acquisition technology", "startup merger handshake"],
        "acquisition": ["business merger technology office", "corporate acquisition news"],
        "detection": ["cybersecurity monitoring screen", "AI fraud detection technology"],
        "ev": ["electric vehicle charging", "battery factory technology"],
        "chip": ["semiconductor fabrication", "computer chip macro"],
        "regulation": ["government technology policy meeting", "capitol building technology"],
    }

    for keyword, visuals in entity_visuals.items():
        if keyword in token_set or keyword in normalized_joined:
            queries.extend(visuals[:2])

    if "gpt" in token_set or re.search(r"\bgpt[\s-]?\d", joined):
        queries.extend(["ChatGPT interface", "AI language model visualization"])
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


def score_video_tag_relevance(relevance_text: str, tags: str) -> float:
    """Score Pixabay/Pexels video tags against an English visual prompt."""
    prompt_tokens = set(_tokenize(relevance_text))
    tag_tokens = set(_tokenize(tags))
    if not prompt_tokens or not tag_tokens:
        return 0.0
    overlap = prompt_tokens & tag_tokens
    return len(overlap) / max(len(prompt_tokens), 1)


def build_section_visual_prompt(
    section_label: str,
    section_text: str,
    story_title: str,
    visual_style: str = "real_footage",
) -> str:
    """Concrete English visual brief for one section."""
    label_tokens = _tokenize(section_label)
    text_tokens = _tokenize(section_text)
    title_tokens = _tokenize(story_title)
    tokens = label_tokens + text_tokens[:8]
    if len(tokens) < 2:
        tokens = title_tokens[:6]

    suffix = style_query_suffix(
        VisualStyle.MOTION_GRAPHICS if visual_style == "motion_graphics" else VisualStyle.REAL_FOOTAGE,
        section_label=section_label,
    )
    core_phrase = " ".join(tokens[:6]).strip()
    if core_phrase:
        return f"{core_phrase} {suffix}".strip()

    entity_queries = _build_entity_queries(title_tokens)
    if entity_queries:
        return entity_queries[0]

    return f"artificial intelligence technology news {suffix}".strip()


def build_section_search_keywords(
    section_label: str,
    section_text: str,
    story_title: str,
    visual_style: str = "real_footage",
    image_search_prompt: str = "",
) -> list[str]:
    """Return 2-4 English stock video queries for one section."""
    prompt = image_search_prompt or build_section_visual_prompt(
        section_label,
        section_text,
        story_title,
        visual_style,
    )
    keywords: list[str] = [prompt]
    section_tokens = _tokenize(f"{section_label} {section_text}")
    if len(section_tokens) >= 2:
        keywords.append(" ".join(section_tokens[:4]))
    keywords.extend(_build_entity_queries(_tokenize(story_title) + section_tokens)[:2])
    suffix = style_query_suffix(
        VisualStyle.MOTION_GRAPHICS if visual_style == "motion_graphics" else VisualStyle.REAL_FOOTAGE,
        section_label=section_label,
    )
    keywords.append(f"{prompt.split()[0]} {suffix}".strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = " ".join(keyword.lower().split())
        if normalized and normalized not in seen:
            deduped.append(keyword.strip())
            seen.add(normalized)
    return deduped[:4]
