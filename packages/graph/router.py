from typing import Literal

from packages.graph.state import AgentState

RouteKey = Literal["approved", "revise", "escalate"]


def route_from_editor(state: AgentState) -> RouteKey:
    if state["is_approved"]:
        return "approved"
    if state["revision_count"] > 3:
        return "escalate"
    return "revise"
