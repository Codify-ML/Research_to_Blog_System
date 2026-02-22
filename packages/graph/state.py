from operator import add
from typing import Annotated, TypedDict

from packages.core.constants import AgentStatus


class AgentState(TypedDict):
    job_id: str
    topic: str
    research_notes: Annotated[list[str], add]
    draft: str
    editor_feedback: Annotated[list[str], add]
    is_approved: bool
    revision_count: int
    status: AgentStatus
    error_message: str | None
