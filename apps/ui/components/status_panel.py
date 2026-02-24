from __future__ import annotations

import json
from typing import Protocol

import streamlit.components.v1 as components

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ESCALATED"}


class StatusPayload(Protocol):
    job_id: str
    llm_mode: str
    max_sources: int
    content_format: str
    content_context: str
    tone: str
    length_preference: str
    research_depth: str
    research_tools_used: list[str]
    status: str
    revision_count: int
    draft: str
    research_notes: list[str]
    editor_feedback: list[str]
    editor_strengths: list[str]
    editor_weaknesses: list[str]
    error_message: str | None
    updated_at: str


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


def terminal_message(payload: StatusPayload) -> str:
    if payload.status == "COMPLETED":
        return "Job completed successfully."
    if payload.error_message:
        return payload.error_message
    if payload.status == "ESCALATED":
        return "Job escalated after exceeding revision threshold."
    return "Job failed without a detailed error message."


def render_status_panel(st, payload: StatusPayload) -> None:
    level = status_level(payload.status)
    message = (
        f"Status: {payload.status} | Mode: {payload.llm_mode.upper()} "
        f"| Revision count: "
        f"{payload.revision_count}"
    )
    getattr(st, level)(message)
    st.caption(f"Job ID: `{payload.job_id}`")
    st.caption(f"Last updated: {payload.updated_at}")
    if payload.research_tools_used:
        st.caption(
            "Research tools used: "
            f"`{', '.join(payload.research_tools_used)}`"
        )
    else:
        st.caption("Research tools used: `none`")
    st.caption(
        "Writing profile: "
        f"`type={payload.content_format}`, "
        f"`tone={payload.tone}`, "
        f"`length={payload.length_preference}`, "
        f"`depth={payload.research_depth}`, "
        f"`max_sources={payload.max_sources}`"
    )
    if payload.content_context:
        st.caption(f"Context: {payload.content_context}")

    with st.expander("Research Notes", expanded=True):
        if payload.research_notes:
            for note in payload.research_notes:
                st.write(f"- {note}")
        else:
            st.write("No research notes available yet.")

    with st.expander("Editorial Assessment", expanded=True):
        st.markdown("**Strengths**")
        if payload.editor_strengths:
            for item in payload.editor_strengths:
                st.write(f"- {item}")
        else:
            st.write("No strengths captured yet.")

        st.markdown("**Weaknesses**")
        if payload.editor_weaknesses:
            for item in payload.editor_weaknesses:
                st.write(f"- {item}")
        else:
            st.write("No weaknesses captured yet.")

    with st.expander("Editor Action Items", expanded=True):
        if payload.editor_feedback:
            for item in payload.editor_feedback:
                st.write(f"- {item}")
        else:
            st.write(
                "No required actions. Draft may already satisfy criteria."
            )

    st.subheader("Draft")
    if payload.draft:
        _render_copy_button(payload.draft)
        with st.container(border=True):
            st.markdown(payload.draft)
    else:
        st.write("Draft not available yet.")


def _render_copy_button(text: str) -> None:
    text_json = json.dumps(text)
    components.html(
        f"""
        <button onclick='copyDraft()'
        style="padding:6px 12px;border-radius:6px;border:1px solid #bbb;">
          Copy Draft
        </button>
        <span id="copy-msg" style="margin-left:8px;font-size:0.9em;"></span>
        <script>
        async function copyDraft() {{
          const msg = document.getElementById("copy-msg");
          try {{
            await navigator.clipboard.writeText({text_json});
            msg.textContent = "Copied.";
          }} catch (err) {{
            msg.textContent = "Copy failed. Use manual copy.";
          }}
        }}
        </script>
        """,
        height=45,
    )
