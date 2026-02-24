from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from packages.core.constants import AgentStatus, LLMMode
from packages.graph.nodes import (
    EditorFn,
    ResearchFn,
    WriterFn,
    escalation_node,
    make_editor_node,
    make_researcher_node,
    make_writer_node,
)
from packages.graph.router import route_from_editor
from packages.graph.state import AgentState


def create_workflow(
    *,
    research_fn: ResearchFn | None = None,
    writer_fn: WriterFn | None = None,
    editor_fn: EditorFn | None = None,
    checkpointer: MemorySaver | None = None,
):
    graph = StateGraph(AgentState)

    graph.add_node("researcher", make_researcher_node(research_fn))
    graph.add_node("writer", make_writer_node(writer_fn))
    graph.add_node("editor", make_editor_node(editor_fn))
    graph.add_node("escalation", escalation_node)

    graph.add_edge(START, "researcher")
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer", "editor")
    graph.add_conditional_edges(
        "editor",
        route_from_editor,
        {
            "approved": END,
            "revise": "writer",
            "escalate": "escalation",
        },
    )
    graph.add_edge("escalation", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())


def initial_state(
    topic: str,
    llm_mode: LLMMode = LLMMode.MOCK,
    max_sources: int = 6,
    content_format: str = "Blog article",
    content_context: str = "",
    tone: str = "professional",
    length_preference: str = "balanced",
    research_depth: str = "standard",
) -> AgentState:
    return {
        "job_id": str(uuid4()),
        "topic": topic,
        "llm_mode": llm_mode,
        "max_sources": max_sources,
        "content_format": content_format,
        "content_context": content_context,
        "tone": tone,
        "length_preference": length_preference,
        "research_depth": research_depth,
        "research_tools_used": [],
        "research_notes": [],
        "draft": "",
        "editor_feedback": [],
        "editor_strengths": [],
        "editor_weaknesses": [],
        "is_approved": False,
        "revision_count": 0,
        "status": AgentStatus.PENDING,
        "error_message": None,
    }


def run_sync(topic: str) -> AgentState:
    app = create_workflow()
    state = initial_state(topic)
    result = app.invoke(
        state, config={"configurable": {"thread_id": state["job_id"]}}
    )
    return result
