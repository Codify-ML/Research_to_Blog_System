from packages.core.constants import AgentStatus
from packages.graph.nodes import make_editor_node
from packages.graph.router import route_from_editor
from packages.graph.schemas import EditorDecision
from packages.graph.state import AgentState


def _state(revision_count: int) -> AgentState:
    return {
        "job_id": "job-1",
        "topic": "topic",
        "research_notes": ["note"],
        "draft": "A sufficiently long draft for evaluation. " * 4,
        "editor_feedback": [],
        "is_approved": False,
        "revision_count": revision_count,
        "status": AgentStatus.RUNNING,
        "error_message": None,
    }


def test_revision_count_increments_on_rejection() -> None:
    def reject_editor(*_args, **_kwargs) -> EditorDecision:
        return EditorDecision(is_approved=False, feedback=["needs work"])

    editor = make_editor_node(reject_editor)
    update = editor(_state(2))
    assert update["revision_count"] == 3
    assert update["is_approved"] is False


def test_route_escalates_after_fourth_rejection() -> None:
    def reject_editor(*_args, **_kwargs) -> EditorDecision:
        return EditorDecision(is_approved=False, feedback=["still not good"])

    editor = make_editor_node(reject_editor)
    base = _state(3)
    update = editor(base)
    merged = {**base, **update}
    assert merged["revision_count"] == 4
    assert route_from_editor(merged) == "escalate"
