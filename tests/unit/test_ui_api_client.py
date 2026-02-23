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
            },
        )
    )
    client = ApiClient(
        base_url="http://127.0.0.1:8000",
        timeout_seconds=5.0,
        session=session,
    )

    result = client.generate("test topic")

    assert result.job_id == "job-123"
    assert result.status == "PENDING"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"] == "http://127.0.0.1:8000/generate"


def test_get_status_maps_payload_and_terminal_property():
    session = _Session(
        response=_Response(
            status_code=200,
            payload={
                "job_id": "job-1",
                "topic": "topic",
                "status": "COMPLETED",
                "revision_count": 1,
                "draft": "final draft",
                "research_notes": ["n1", "n2"],
                "editor_feedback": [],
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
        client.generate("queue outage")

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
