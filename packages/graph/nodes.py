from collections.abc import Callable

from packages.core.constants import AgentStatus
from packages.graph.schemas import EditorDecision
from packages.graph.state import AgentState

ResearchFn = Callable[[str], tuple[list[str], str]]
WriterFn = Callable[[str, list[str], list[str], str], str]
EditorFn = Callable[[str, str, list[str], int], EditorDecision]


def default_research(topic: str) -> tuple[list[str], str]:
    notes = [
        f"Define the problem space for: {topic}.",
        f"List practical implementation constraints for: {topic}.",
        f"Capture risks and mitigations relevant to: {topic}.",
    ]
    summary = f"Structured starter research generated for topic: {topic}."
    return notes, summary


def default_writer(
    topic: str,
    research_notes: list[str],
    feedback: list[str],
    prior_draft: str,
) -> str:
    feedback_block = (
        "\n".join(f"- Address: {item}" for item in feedback)
        or "- No pending edits."
    )
    notes_block = "\n".join(f"- {item}" for item in research_notes)
    intro = (
        f"# {topic}\n\nThis draft is grounded in structured research notes."
    )
    if prior_draft:
        intro += "\n\nThis is a revised version of the existing draft."
    return (
        f"{intro}\n\n## Research Notes\n{notes_block}\n\n"
        f"## Revision Goals\n{feedback_block}\n"
    )


def default_editor(
    topic: str, draft: str, research_notes: list[str], revision_count: int
) -> EditorDecision:
    if "FORCE_ESCALATE" in topic:
        return EditorDecision(
            is_approved=False,
            feedback=["Forced escalation for deterministic testing."],
        )

    if len(draft.strip()) < 120:
        return EditorDecision(
            is_approved=False,
            feedback=[
                "Draft is too short; expand with clearer structure and detail."
            ],
        )

    if not research_notes:
        return EditorDecision(
            is_approved=False,
            feedback=["Research notes are required to approve the draft."],
        )

    # Deterministic approval condition for Phase 1 harness/tests.
    if revision_count >= 1:
        return EditorDecision(is_approved=True, feedback=[])
    return EditorDecision(
        is_approved=False,
        feedback=[
            "Address structure and clarity issues, then resubmit for review."
        ],
    )


def make_researcher_node(
    research_fn: ResearchFn | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    research_impl = research_fn or default_research

    def researcher_node(state: AgentState) -> dict[str, object]:
        notes, _summary = research_impl(state["topic"])
        return {
            "status": AgentStatus.RUNNING,
            "research_notes": notes,
            "error_message": None,
        }

    return researcher_node


def make_writer_node(
    writer_fn: WriterFn | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    writer_impl = writer_fn or default_writer

    def writer_node(state: AgentState) -> dict[str, object]:
        draft = writer_impl(
            state["topic"],
            state["research_notes"],
            state["editor_feedback"],
            state["draft"],
        )
        return {
            "status": AgentStatus.RUNNING,
            "draft": draft,
            "error_message": None,
        }

    return writer_node


def make_editor_node(
    editor_fn: EditorFn | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    editor_impl = editor_fn or default_editor

    def editor_node(state: AgentState) -> dict[str, object]:
        decision = editor_impl(
            state["topic"],
            state["draft"],
            state["research_notes"],
            state["revision_count"],
        )

        if decision.is_approved:
            return {
                "status": AgentStatus.COMPLETED,
                "is_approved": True,
                "error_message": None,
            }

        return {
            "status": AgentStatus.RUNNING,
            "is_approved": False,
            "editor_feedback": decision.feedback,
            "revision_count": state["revision_count"] + 1,
            "error_message": None,
        }

    return editor_node


def escalation_node(state: AgentState) -> dict[str, object]:
    return {
        "status": AgentStatus.ESCALATED,
        "is_approved": False,
        "error_message": (
            "Editor rejected the draft more than 3 times. "
            "Escalated to failure path as loop guard protection."
        ),
    }
