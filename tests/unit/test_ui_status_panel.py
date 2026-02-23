from __future__ import annotations

from apps.ui.api_client import StatusResult
from apps.ui.components.status_panel import (
    is_terminal_status,
    status_level,
    terminal_message,
)


def _status_payload(
    *,
    status: str,
    error_message: str | None = None,
) -> StatusResult:
    return StatusResult(
        job_id="job-1",
        topic="topic",
        status=status,
        revision_count=2,
        draft="draft text",
        research_notes=["note"],
        editor_feedback=["feedback"],
        error_message=error_message,
        updated_at="2026-02-23T00:00:00+00:00",
    )


def test_terminal_status_detection():
    assert is_terminal_status("COMPLETED") is True
    assert is_terminal_status("ESCALATED") is True
    assert is_terminal_status("RUNNING") is False


def test_status_level_mapping():
    assert status_level("COMPLETED") == "success"
    assert status_level("FAILED") == "error"
    assert status_level("ESCALATED") == "error"
    assert status_level("RETRYING") == "warning"
    assert status_level("PENDING") == "info"


def test_terminal_message_uses_error_message_when_present():
    payload = _status_payload(
        status="FAILED",
        error_message="Detailed failure reason.",
    )
    assert terminal_message(payload) == "Detailed failure reason."


def test_terminal_message_defaults_for_escalation():
    payload = _status_payload(status="ESCALATED")
    assert "exceeding revision threshold" in terminal_message(payload)
