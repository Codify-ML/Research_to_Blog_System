from __future__ import annotations

from packages.graph.prompts import (
    EDITOR_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    build_researcher_user_prompt,
    build_writer_user_prompt,
    compose_prompt,
)
from packages.graph.research_tools import (
    freshness_window_days,
    is_freshness_critical,
    normalize_sources,
    score_sources,
    should_use_web_search,
)


def test_should_use_web_search_for_freshness_signals() -> None:
    assert should_use_web_search("latest OpenAI model releases in 2026")
    assert should_use_web_search("today's AWS outage trends")


def test_should_use_web_search_false_for_stable_topic() -> None:
    assert not should_use_web_search("python decorators explained")


def test_freshness_critical_and_window_for_market_queries() -> None:
    topic = "Intuit stock now"
    assert is_freshness_critical(topic)
    assert freshness_window_days(topic) == 3


def test_normalize_sources_deduplicates() -> None:
    payload = {
        "sources": [
            {
                "url": "https://example.com/a",
                "title": "A",
                "snippet": "alpha",
                "domain": "example.com",
            },
            {
                "url": "https://example.com/a",
                "title": "A",
                "snippet": "alpha",
                "domain": "example.com",
            },
        ]
    }
    result = normalize_sources(payload)
    assert len(result["sources"]) == 1
    assert result["sources"][0]["content_hash"]


def test_score_sources_returns_descending_scores() -> None:
    payload = {
        "topic": "openai platform updates",
        "sources": [
            {
                "title": "OpenAI platform updates",
                "snippet": "latest platform changes",
                "domain": "openai.com",
                "published_at": "2026-02-01T00:00:00+00:00",
            },
            {
                "title": "Generic blog",
                "snippet": "old unrelated article",
                "domain": "example.net",
                "published_at": "2020-01-01T00:00:00+00:00",
            },
        ],
    }
    result = score_sources(payload)
    scores = [item["score"] for item in result["sources"]]
    assert scores == sorted(scores, reverse=True)


def test_prompts_are_centralized_and_composable() -> None:
    prompt = compose_prompt(
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        user_prompt="Topic: test",
    )
    assert "SYSTEM" in prompt
    assert "USER" in prompt
    assert "Researcher agent" in RESEARCHER_SYSTEM_PROMPT
    assert "Writer agent" in WRITER_SYSTEM_PROMPT
    assert "Editor agent" in EDITOR_SYSTEM_PROMPT


def test_research_prompt_includes_reference_date_and_freshness_policy() -> (
    None
):
    prompt = build_researcher_user_prompt(
        topic="Intuit stock now",
        reference_date="2026-02-23",
        freshness_critical=True,
        freshness_window_days=3,
        web_search_enabled=True,
        max_sources=5,
        content_format="LinkedIn post",
        length_preference="short",
        research_depth="standard",
    )
    assert "Reference date (UTC): 2026-02-23" in prompt
    assert "last 3 day(s)" in prompt
    assert "Use the web search tool" in prompt
    assert "at most 5 distinct sources" in prompt
    assert "Research depth: standard" in prompt
    assert "Return 4 to 7 bullet points." in prompt
    assert "Every bullet must include citation metadata" in prompt
    assert "url: <https://... or n/a>" in prompt


def test_writer_prompt_adds_linkedin_emoji_guidance() -> None:
    prompt = build_writer_user_prompt(
        topic="AI in product teams",
        research_notes=["note one"],
        feedback=[],
        prior_draft="",
        content_format="LinkedIn post",
        content_context="for startup founders",
        tone="professional",
        length_preference="short",
    )
    assert "optional emoji (0-3)" in prompt
