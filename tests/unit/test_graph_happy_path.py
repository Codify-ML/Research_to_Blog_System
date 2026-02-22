from packages.graph.schemas import EditorDecision
from packages.graph.workflow import create_workflow, initial_state


def test_graph_happy_path_completes_before_escalation() -> None:
    approvals = [
        EditorDecision(is_approved=False, feedback=["improve structure"]),
        EditorDecision(is_approved=True, feedback=[]),
    ]

    def editor_fn(*_args, **_kwargs) -> EditorDecision:
        return approvals.pop(0)

    app = create_workflow(editor_fn=editor_fn)
    state = initial_state("happy topic")
    result = app.invoke(
        state, config={"configurable": {"thread_id": state["job_id"]}}
    )

    assert result["status"] == "COMPLETED"
    assert result["is_approved"] is True
    assert result["revision_count"] == 1
    assert len(result["draft"]) > 0
