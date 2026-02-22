from packages.graph.schemas import EditorDecision
from packages.graph.workflow import create_workflow, initial_state


def test_graph_forced_escalation_at_revision_four() -> None:
    def editor_fn(*_args, **_kwargs) -> EditorDecision:
        return EditorDecision(is_approved=False, feedback=["not acceptable"])

    app = create_workflow(editor_fn=editor_fn)
    state = initial_state("topic that keeps failing")
    result = app.invoke(
        state, config={"configurable": {"thread_id": state["job_id"]}}
    )

    assert result["status"] == "ESCALATED"
    assert result["is_approved"] is False
    assert result["revision_count"] == 4
    assert "loop guard" in (result["error_message"] or "")
