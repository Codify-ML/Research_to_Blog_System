from collections.abc import Callable

from packages.core.constants import AgentStatus
from packages.graph.schemas import EditorDecision
from packages.graph.state import AgentState

ResearchFn = Callable[
    [str, int, str, str, str],
    tuple[list[str], str, list[str]],
]
WriterFn = Callable[
    [str, list[str], list[str], str, str, str, str, str],
    str,
]
EditorFn = Callable[
    [str, str, list[str], int, str, str, str],
    EditorDecision,
]


def default_research(
    topic: str,
    max_sources: int,
    content_format: str,
    length_preference: str,
    research_depth: str,
) -> tuple[list[str], str, list[str]]:
    del max_sources
    del content_format
    del length_preference
    del research_depth
    notes = [
        (
            f"Define the problem space for: {topic}. "
            "[source: internal mock knowledge; url: n/a; "
            "date: unknown]"
        ),
        (
            f"List practical implementation constraints for: {topic}. "
            "[source: internal mock knowledge; url: n/a; "
            "date: unknown]"
        ),
        (
            f"Capture risks and mitigations relevant to: {topic}. "
            "[source: internal mock knowledge; url: n/a; "
            "date: unknown]"
        ),
    ]
    summary = f"Structured starter research generated for topic: {topic}."
    return notes, summary, []


def default_writer(
    topic: str,
    research_notes: list[str],
    feedback: list[str],
    prior_draft: str,
    content_format: str,
    content_context: str,
    tone: str,
    length_preference: str,
) -> str:
    feedback_block = (
        "\n".join(f"- Address: {item}" for item in feedback)
        or "- No pending edits."
    )
    notes_block = "\n".join(f"- {item}" for item in research_notes)
    intro = (
        f"# {topic}\n\nThis draft is grounded in structured research notes."
    )
    intro += (
        f"\n\nTarget format: {content_format}."
        f" Tone: {tone}. Length: {length_preference}."
    )
    if content_context:
        intro += f"\n\nContext: {content_context}"
    if prior_draft:
        intro += "\n\nThis is a revised version of the existing draft."
    return (
        f"{intro}\n\n## Research Notes\n{notes_block}\n\n"
        f"## Revision Goals\n{feedback_block}\n"
    )


def default_editor(
    topic: str,
    draft: str,
    research_notes: list[str],
    revision_count: int,
    content_format: str,
    tone: str,
    length_preference: str,
) -> EditorDecision:
    strengths = [
        "The draft has a clear topic focus.",
        f"Format target '{content_format}' is acknowledged.",
        f"Tone target '{tone}' is considered in the structure.",
    ]
    weaknesses: list[str] = []

    if "FORCE_ESCALATE" in topic:
        return EditorDecision(
            is_approved=False,
            feedback=["Forced escalation for deterministic testing."],
            strengths=strengths,
            weaknesses=["Forced escalation path requested."],
        )

    if len(draft.strip()) < 120:
        weaknesses.append("Draft length is too short for clarity.")
        return EditorDecision(
            is_approved=False,
            feedback=[
                "Draft is too short; expand with clearer structure and detail."
            ],
            strengths=strengths,
            weaknesses=weaknesses,
        )

    if not research_notes:
        weaknesses.append("Draft is not grounded in research notes.")
        return EditorDecision(
            is_approved=False,
            feedback=["Research notes are required to approve the draft."],
            strengths=strengths,
            weaknesses=weaknesses,
        )

    # Deterministic approval condition for Phase 1 harness/tests.
    if revision_count >= 1:
        strengths.append(
            f"Length preference '{length_preference}' appears respected."
        )
        return EditorDecision(
            is_approved=True,
            feedback=["Optional: add one concrete real-world example."],
            strengths=strengths,
            weaknesses=["Could improve with additional concrete examples."],
        )
    weaknesses.append("Initial draft still needs stronger structure.")
    return EditorDecision(
        is_approved=False,
        feedback=[
            "Address structure and clarity issues, then resubmit for review."
        ],
        strengths=strengths,
        weaknesses=weaknesses,
    )


def make_researcher_node(
    research_fn: ResearchFn | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    research_impl = research_fn or default_research

    def researcher_node(state: AgentState) -> dict[str, object]:
        notes, _summary, tools_used = research_impl(
            state["topic"],
            state["max_sources"],
            state["content_format"],
            state["length_preference"],
            state["research_depth"],
        )
        return {
            "status": AgentStatus.RUNNING,
            "research_tools_used": tools_used,
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
            state["content_format"],
            state["content_context"],
            state["tone"],
            state["length_preference"],
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
            state["content_format"],
            state["tone"],
            state["length_preference"],
        )

        if decision.is_approved:
            return {
                "status": AgentStatus.COMPLETED,
                "is_approved": True,
                "editor_feedback": decision.feedback,
                "editor_strengths": decision.strengths,
                "editor_weaknesses": decision.weaknesses,
                "error_message": None,
            }

        return {
            "status": AgentStatus.RUNNING,
            "is_approved": False,
            "editor_feedback": decision.feedback,
            "editor_strengths": decision.strengths,
            "editor_weaknesses": decision.weaknesses,
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
