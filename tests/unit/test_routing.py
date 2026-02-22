from packages.core.constants import AgentStatus
from packages.graph.router import route_from_editor
from packages.graph.state import AgentState


def _base_state() -> AgentState:
    return {
        "job_id": "job-1",
        "topic": "topic",
        "research_notes": [],
        "draft": "draft",
        "editor_feedback": [],
        "is_approved": False,
        "revision_count": 0,
        "status": AgentStatus.RUNNING,
        "error_message": None,
    }


def test_route_approved() -> None:
    state = _base_state()
    state["is_approved"] = True
    assert route_from_editor(state) == "approved"


def test_route_revise_when_under_threshold() -> None:
    state = _base_state()
    state["revision_count"] = 3
    assert route_from_editor(state) == "revise"


def test_route_escalate_when_over_threshold() -> None:
    state = _base_state()
    state["revision_count"] = 4
    assert route_from_editor(state) == "escalate"
