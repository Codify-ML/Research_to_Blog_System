from operator import add
from typing import Annotated, TypedDict

from packages.core.constants import AgentStatus, LLMMode


class AgentState(TypedDict):
    job_id: str
    topic: str
    llm_mode: LLMMode
    max_sources: int
    content_format: str
    content_context: str
    tone: str
    length_preference: str
    research_depth: str
    research_tools_used: Annotated[list[str], add]
    research_notes: Annotated[list[str], add]
    draft: str
    editor_feedback: Annotated[list[str], add]
    editor_strengths: Annotated[list[str], add]
    editor_weaknesses: Annotated[list[str], add]
    is_approved: bool
    revision_count: int
    status: AgentStatus
    error_message: str | None
