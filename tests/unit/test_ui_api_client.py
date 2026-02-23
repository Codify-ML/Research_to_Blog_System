from __future__ import annotations

import pytest
import requests

from apps.ui.api_client import ApiClient, ApiClientError


class _Response:
    def __init__(
        self,
        *,
        status_code: int,
        payload: dict | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("No JSON payload available.")
        return self._payload


class _Session:
    def __init__(
        self,
        *,
        response: _Response | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.response = response
        self.exception = exception
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        if self.exception is not None:
            raise self.exception
        return self.response


def test_generate_success_maps_response_fields():
    session = _Session(
        response=_Response(
            status_code=200,
            payload={
                "job_id": "job-123",
                "status": "PENDING",
                "llm_mode": "mock",
            },
        )
    )
    client = ApiClient(
        base_url="http://127.0.0.1:8000",
        timeout_seconds=5.0,
        session=session,
    )

    result = client.generate(
        topic="test topic",
        llm_mode="mock",
        max_sources=6,
        content_format="Blog article",
        content_context="",
        tone="professional",
        length_preference="balanced",
        research_depth="standard",
    )

    assert result.job_id == "job-123"
    assert result.status == "PENDING"
    assert result.llm_mode == "mock"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"] == "http://127.0.0.1:8000/generate"
    assert session.calls[0]["json"]["llm_mode"] == "mock"
    assert session.calls[0]["json"]["max_sources"] == 6
    assert session.calls[0]["json"]["research_depth"] == "standard"


def test_get_status_maps_payload_and_terminal_property():
    session = _Session(
        response=_Response(
            status_code=200,
            payload={
                "job_id": "job-1",
                "topic": "topic",
                "llm_mode": "openai",
                "research_tools_used": [
                    "web_search",
                    "function:normalize_sources",
                ],
                "max_sources": 5,
                "content_format": "LinkedIn post",
                "content_context": "For engineering leaders.",
                "tone": "professional",
                "length_preference": "short",
                "research_depth": "deep",
                "status": "COMPLETED",
                "revision_count": 1,
                "draft": "final draft",
                "research_notes": ["n1", "n2"],
                "editor_feedback": [],
                "editor_strengths": ["Clear structure."],
                "editor_weaknesses": ["Could use stronger examples."],
                "error_message": None,
                "updated_at": "2026-02-23T00:00:00+00:00",
            },
        )
    )
    client = ApiClient(
        base_url="http://127.0.0.1:8000",
        timeout_seconds=5.0,
        session=session,
    )

    result = client.get_status("job-1")

    assert result.job_id == "job-1"
    assert result.llm_mode == "openai"
    assert result.research_tools_used == [
        "web_search",
        "function:normalize_sources",
    ]
    assert result.max_sources == 5
    assert result.content_format == "LinkedIn post"
    assert result.tone == "professional"
    assert result.length_preference == "short"
    assert result.research_depth == "deep"
    assert result.editor_strengths == ["Clear structure."]
    assert result.editor_weaknesses == ["Could use stronger examples."]
    assert result.research_notes == ["n1", "n2"]
    assert result.is_terminal is True


def test_api_error_raises_contract_aware_exception():
    session = _Session(
        response=_Response(
            status_code=503,
            payload={
                "detail": {
                    "code": "QUEUE_UNAVAILABLE",
                    "message": "Queue is unavailable.",
                }
            },
        )
    )
    client = ApiClient(
        base_url="http://127.0.0.1:8000",
        timeout_seconds=5.0,
        session=session,
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.generate(
            topic="queue outage",
            llm_mode="mock",
            max_sources=6,
            content_format="Blog article",
            content_context="",
            tone="professional",
            length_preference="balanced",
            research_depth="standard",
        )

    exc = exc_info.value
    assert exc.status_code == 503
    assert exc.error_code == "QUEUE_UNAVAILABLE"
    assert "Queue is unavailable" in str(exc)


def test_transport_error_is_wrapped():
    session = _Session(
        exception=requests.RequestException("connection failed")
    )
    client = ApiClient(
        base_url="http://127.0.0.1:8000",
        timeout_seconds=5.0,
        session=session,
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.get_status("job-2")

    assert "Request to API failed" in str(exc_info.value)
