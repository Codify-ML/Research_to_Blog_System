from collections.abc import Callable

from packages.core.constants import AgentStatus
from packages.core.observability import get_observability, update_span
from packages.core.settings import get_settings
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


def _capture_content_enabled() -> bool:
    return get_settings().langfuse_capture_content


def _as_observability_payload(
    payload: dict[str, object],
) -> dict[str, object] | None:
    if not _capture_content_enabled():
        return None
    return payload


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
        settings = get_settings()
        observability = get_observability(settings)
        with observability.span(
            name="graph.node.researcher",
            input_payload=_as_observability_payload(
                {
                    "topic": state["topic"],
                    "max_sources": state["max_sources"],
                    "research_depth": state["research_depth"],
                }
            ),
            metadata={"job_id": state["job_id"]},
        ) as span:
            notes, _summary, tools_used = research_impl(
                state["topic"],
                state["max_sources"],
                state["content_format"],
                state["length_preference"],
                state["research_depth"],
            )
            output = {
                "status": AgentStatus.RUNNING,
                "research_tools_used": tools_used,
                "research_notes": notes,
                "error_message": None,
            }
            update_span(
                span,
                output_payload=_as_observability_payload(
                    {
                        "note_count": len(notes),
                        "research_notes": notes,
                        "tools_used": tools_used,
                    }
                ),
                metadata={
                    "note_count": len(notes),
                    "tool_count": len(tools_used),
                },
            )
            return output

    return researcher_node


def make_writer_node(
    writer_fn: WriterFn | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    writer_impl = writer_fn or default_writer

    def writer_node(state: AgentState) -> dict[str, object]:
        settings = get_settings()
        observability = get_observability(settings)
        with observability.span(
            name="graph.node.writer",
            input_payload=_as_observability_payload(
                {
                    "topic": state["topic"],
                    "research_notes": state["research_notes"],
                    "editor_feedback": state["editor_feedback"],
                    "tone": state["tone"],
                    "length_preference": state["length_preference"],
                }
            ),
            metadata={"job_id": state["job_id"]},
        ) as span:
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
            output = {
                "status": AgentStatus.RUNNING,
                "draft": draft,
                "error_message": None,
            }
            update_span(
                span,
                output_payload=_as_observability_payload(
                    {"draft": draft}
                ),
                metadata={"draft_char_count": len(draft)},
            )
            return output

    return writer_node


def make_editor_node(
    editor_fn: EditorFn | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    editor_impl = editor_fn or default_editor

    def editor_node(state: AgentState) -> dict[str, object]:
        settings = get_settings()
        observability = get_observability(settings)
        with observability.span(
            name="graph.node.editor",
            input_payload=_as_observability_payload(
                {
                    "topic": state["topic"],
                    "draft": state["draft"],
                    "research_notes": state["research_notes"],
                    "revision_count": state["revision_count"],
                }
            ),
            metadata={"job_id": state["job_id"]},
        ) as span:
            decision = editor_impl(
                state["topic"],
                state["draft"],
                state["research_notes"],
                state["revision_count"],
                state["content_format"],
                state["tone"],
                state["length_preference"],
            )

            update_span(
                span,
                output_payload=_as_observability_payload(
                    {
                        "is_approved": decision.is_approved,
                        "feedback": decision.feedback,
                        "strengths": decision.strengths,
                        "weaknesses": decision.weaknesses,
                    }
                ),
                metadata={
                    "approved": decision.is_approved,
                    "feedback_count": len(decision.feedback),
                    "strength_count": len(decision.strengths),
                    "weakness_count": len(decision.weaknesses),
                },
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
    settings = get_settings()
    observability = get_observability(settings)
    with observability.span(
        name="graph.node.escalation",
        metadata={"job_id": state["job_id"]},
    ) as span:
        output = {
            "status": AgentStatus.ESCALATED,
            "is_approved": False,
            "error_message": (
                "Editor rejected the draft more than 3 times. "
                "Escalated to failure path as loop guard protection."
            ),
        }
        update_span(
            span,
            output_payload=_as_observability_payload(output),
            metadata={"escalated": True},
            level="WARNING",
            status_message=str(output["error_message"]),
        )
        return output
