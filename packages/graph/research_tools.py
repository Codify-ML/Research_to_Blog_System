from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

CURRENT_YEAR = datetime.now(tz=UTC).year

WEB_SEARCH_SIGNAL_TERMS = {
    "latest",
    "recent",
    "today",
    "current",
    "now",
    "news",
    "update",
    "updates",
    "price",
    "pricing",
    "release",
    "roadmap",
    "version",
    "benchmark",
    "policy",
    "regulation",
}

FRESHNESS_CRITICAL_TERMS = {
    "now",
    "today",
    "current",
    "latest",
    "stock",
    "price",
    "market",
    "quote",
    "shares",
    "earnings",
}

TRUSTED_DOMAIN_BOOSTS = {
    "openai.com": 0.12,
    "docs.python.org": 0.10,
    "ietf.org": 0.10,
    "w3.org": 0.10,
    "aws.amazon.com": 0.08,
    "cloud.google.com": 0.08,
}


def should_use_web_search(topic: str) -> bool:
    lowered = topic.lower()

    if any(term in lowered for term in WEB_SEARCH_SIGNAL_TERMS):
        return True

    for year in range(CURRENT_YEAR - 1, CURRENT_YEAR + 2):
        if str(year) in lowered:
            return True

    return False


def is_freshness_critical(topic: str) -> bool:
    lowered = topic.lower()
    if any(term in lowered for term in FRESHNESS_CRITICAL_TERMS):
        return True

    for year in range(CURRENT_YEAR - 1, CURRENT_YEAR + 2):
        if str(year) in lowered:
            return True

    return False


def freshness_window_days(topic: str) -> int:
    lowered = topic.lower()
    market_terms = {"stock", "price", "market", "quote", "shares"}
    if any(term in lowered for term in market_terms):
        return 3
    return 30


def normalize_sources(args: dict[str, Any]) -> dict[str, Any]:
    raw_items = args.get("sources", [])
    if not isinstance(raw_items, list):
        return {"sources": []}

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        domain = str(item.get("domain", "")).strip().lower()
        published_at = str(item.get("published_at", "")).strip() or None

        if not url and not title:
            continue

        key_basis = f"{url}|{title}|{snippet[:80]}"
        content_hash = hashlib.sha256(key_basis.encode("utf-8")).hexdigest()
        if content_hash in seen:
            continue
        seen.add(content_hash)

        normalized.append(
            {
                "url": url,
                "title": title,
                "snippet": snippet,
                "domain": domain,
                "published_at": published_at,
                "source_type": "web",
                "content_hash": content_hash,
            }
        )

    return {"sources": normalized}


def score_sources(args: dict[str, Any]) -> dict[str, Any]:
    sources = args.get("sources", [])
    topic = str(args.get("topic", "")).lower()
    if not isinstance(sources, list):
        return {"sources": []}

    scored: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue

        title = str(source.get("title", "")).lower()
        snippet = str(source.get("snippet", "")).lower()
        domain = str(source.get("domain", "")).lower()

        relevance = _keyword_overlap_score(topic, f"{title} {snippet}")
        credibility = _domain_credibility_score(domain)
        freshness = _freshness_score(str(source.get("published_at", "")))

        score = round(
            (0.5 * relevance) + (0.3 * credibility) + (0.2 * freshness), 4
        )
        enriched = dict(source)
        enriched["score"] = score
        scored.append(enriched)

    scored.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return {"sources": scored}


def get_research_function_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "normalize_sources",
            "description": (
                "Normalize, deduplicate, and canonicalize discovered sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "description": "Raw source candidates.",
                        "items": {"type": "object"},
                    }
                },
                "required": ["sources"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "score_sources",
            "description": (
                "Score normalized sources for relevance, credibility, and "
                "freshness."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "sources": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
                "required": ["topic", "sources"],
                "additionalProperties": False,
            },
        },
    ]


def get_research_function_handlers() -> dict[str, Any]:
    return {
        "normalize_sources": normalize_sources,
        "score_sources": score_sources,
    }


def _keyword_overlap_score(topic: str, source_text: str) -> float:
    topic_words = {word for word in topic.split() if len(word) > 2}
    if not topic_words:
        return 0.0

    hits = sum(1 for word in topic_words if word in source_text)
    return min(1.0, hits / max(1, len(topic_words)))


def _domain_credibility_score(domain: str) -> float:
    if not domain:
        return 0.3
    for trusted, boost in TRUSTED_DOMAIN_BOOSTS.items():
        if domain.endswith(trusted):
            return min(1.0, 0.7 + boost)
    return 0.6


def _freshness_score(published_at: str) -> float:
    if not published_at:
        return 0.4

    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.4

    age_days = max(0, (datetime.now(tz=UTC) - dt).days)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.8
    if age_days <= 365:
        return 0.6
    return 0.4
