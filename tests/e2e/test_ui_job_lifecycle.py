from __future__ import annotations

from apps.ui import app as ui_app
from apps.ui.api_client import GenerateResult, StatusResult
from apps.ui.components.status_panel import (
    is_terminal_status,
    terminal_message,
)
from packages.core.constants import LLMMode


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}


class _HappyClient:
    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []

    def generate(self, **kwargs) -> GenerateResult:
        self.generate_calls.append(kwargs)
        return GenerateResult(
            job_id="job-happy",
            status="PENDING",
            llm_mode="mock",
        )

    def get_status(self, _job_id: str) -> StatusResult:
        return StatusResult(
            job_id="job-happy",
            topic="Happy topic",
            llm_mode="mock",
            max_sources=6,
            content_format="Blog article",
            content_context="For platform engineers.",
            tone="professional",
            length_preference="balanced",
            research_depth="standard",
            research_tools_used=["web_search"],
            status="COMPLETED",
            revision_count=1,
            draft="Final draft",
            research_notes=["Note 1", "Note 2"],
            editor_feedback=["Optional improvement"],
            editor_strengths=["Clear structure."],
            editor_weaknesses=["Could include one more example."],
            error_message=None,
            updated_at="2026-02-23T00:00:00+00:00",
        )


class _EscalationClient:
    def generate(self, **_kwargs) -> GenerateResult:
        return GenerateResult(
            job_id="job-escalated",
            status="PENDING",
            llm_mode="mock",
        )

    def get_status(self, _job_id: str) -> StatusResult:
        return StatusResult(
            job_id="job-escalated",
            topic="Escalation topic",
            llm_mode="mock",
            max_sources=8,
            content_format="LinkedIn post",
            content_context="For founders.",
            tone="persuasive",
            length_preference="short",
            research_depth="deep",
            research_tools_used=[],
            status="ESCALATED",
            revision_count=4,
            draft="",
            research_notes=["Note A"],
            editor_feedback=["Needs major rewrite"],
            editor_strengths=["Relevant topic selection."],
            editor_weaknesses=["Insufficient evidence and clarity."],
            error_message="Escalated after repeated non-approval.",
            updated_at="2026-02-23T00:01:00+00:00",
        )


def test_ui_happy_path_lifecycle_resets_and_tracks_new_job(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ui_app, "st", fake_st)

    ui_app._init_session_state()
    fake_st.session_state["active_job_id"] = "stale-job"
    fake_st.session_state["latest_status"] = "stale-status"
    fake_st.session_state["ui_error"] = "stale-error"
    fake_st.session_state["active_generation_options"] = {"old": "value"}

    ui_app._clear_active_run()
    assert fake_st.session_state["active_job_id"] is None
    assert fake_st.session_state["latest_status"] is None
    assert fake_st.session_state["ui_error"] is None
    assert fake_st.session_state["active_generation_options"] == {}

    client = _HappyClient()
    ui_app._submit_topic(
        client,
        topic="Happy topic",
        llm_mode=LLMMode.MOCK,
        max_sources=6,
        content_format="Blog article",
        content_context="For platform engineers.",
        tone="professional",
        length_preference="balanced",
        research_depth="standard",
    )

    assert fake_st.session_state["active_job_id"] == "job-happy"
    assert fake_st.session_state["active_llm_mode"] == "mock"
    assert client.generate_calls

    payload = ui_app._fetch_status(client, "job-happy")
    assert payload is not None
    assert payload.status == "COMPLETED"
    assert is_terminal_status(payload.status)
    assert terminal_message(payload) == "Job completed successfully."


def test_ui_escalation_path_surfaces_terminal_failure_message(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ui_app, "st", fake_st)
    ui_app._init_session_state()

    client = _EscalationClient()
    ui_app._submit_topic(
        client,
        topic="Escalation topic",
        llm_mode=LLMMode.MOCK,
        max_sources=8,
        content_format="LinkedIn post",
        content_context="For founders.",
        tone="persuasive",
        length_preference="short",
        research_depth="deep",
    )

    payload = ui_app._fetch_status(client, "job-escalated")
    assert payload is not None
    assert payload.status == "ESCALATED"
    assert payload.revision_count == 4
    assert is_terminal_status(payload.status)
    assert terminal_message(payload) == (
        "Escalated after repeated non-approval."
    )
