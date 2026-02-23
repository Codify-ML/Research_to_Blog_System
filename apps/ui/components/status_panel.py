from __future__ import annotations

from apps.ui.api_client import StatusResult

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ESCALATED"}


def is_terminal_status(status: str) -> bool:
    return status in TERMINAL_STATUSES


def status_level(status: str) -> str:
    if status == "COMPLETED":
        return "success"
    if status in {"FAILED", "ESCALATED"}:
        return "error"
    if status == "RETRYING":
        return "warning"
    return "info"


def terminal_message(payload: StatusResult) -> str:
    if payload.status == "COMPLETED":
        return "Job completed successfully."
    if payload.error_message:
        return payload.error_message
    if payload.status == "ESCALATED":
        return "Job escalated after exceeding revision threshold."
    return "Job failed without a detailed error message."


def render_status_panel(st, payload: StatusResult) -> None:
    level = status_level(payload.status)
    message = (
        f"Status: {payload.status} | Revision count: "
        f"{payload.revision_count}"
    )
    getattr(st, level)(message)
    st.caption(f"Job ID: `{payload.job_id}`")
    st.caption(f"Last updated: {payload.updated_at}")

    with st.expander("Research Notes", expanded=True):
        if payload.research_notes:
            for note in payload.research_notes:
                st.write(f"- {note}")
        else:
            st.write("No research notes available yet.")

    with st.expander("Editor Feedback", expanded=True):
        if payload.editor_feedback:
            for item in payload.editor_feedback:
                st.write(f"- {item}")
        else:
            st.write("No editor feedback recorded.")

    st.subheader("Draft")
    if payload.draft:
        st.text_area(
            "Current Draft",
            value=payload.draft,
            height=280,
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.write("Draft not available yet.")
