from __future__ import annotations

from packages.graph.agent_factory import _ensure_citation_metadata


def test_ensure_citation_metadata_adds_placeholder_when_missing() -> None:
    notes = ["Revenue grew 12% year-over-year."]

    normalized = _ensure_citation_metadata(notes)

    assert len(normalized) == 1
    assert "[source: n/a; url: n/a; date: unknown]" in normalized[0]


def test_ensure_citation_metadata_keeps_existing_url_citation() -> None:
    notes = [
        (
            "Revenue grew 12% year-over-year. "
            "Source: https://example.com/report"
        )
    ]

    normalized = _ensure_citation_metadata(notes)

    assert normalized == notes
