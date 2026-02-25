from __future__ import annotations

import json
import re
from typing import Protocol
from urllib.parse import urlparse

import streamlit.components.v1 as components

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ESCALATED"}
_URL_PATTERN = re.compile(r"https?://[^\s\])>]+")
_CITATION_BLOCK_PATTERN = re.compile(
    r"\[(?:source|citation)\s*:\s*([^\]]+)\]",
    re.IGNORECASE,
)


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
    created_at: str
    updated_at: str
    status_transitions: list[dict[str, str | None]]


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


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def _status_path(payload: StatusPayload) -> str:
    if not payload.status_transitions:
        return payload.status

    labels: list[str] = []
    for step in payload.status_transitions:
        target = step.get("to")
        if target:
            labels.append(str(target))
    if not labels:
        return payload.status
    return " -> ".join(labels)


def _render_section_header(st, title: str, subtitle: str = "") -> None:
    extra = f"<span class='rtb-sub'>{subtitle}</span>" if subtitle else ""
    st.markdown(
        (
            "<div class='rtb-section-h'>"
            f"<span class='rtb-title'>{title}</span>"
            f"{extra}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_stage_summary(st, payload: StatusPayload) -> None:
    notes_count = len(payload.research_notes)
    tools_count = len(payload.research_tools_used)
    feedback_count = len(payload.editor_feedback)
    strengths_count = len(payload.editor_strengths)
    weaknesses_count = len(payload.editor_weaknesses)

    with st.container(border=True):
        _render_section_header(
            st,
            "Stage Summary",
            "high-level per-agent output",
        )
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            with st.container(border=True):
                st.markdown("**Researcher**")
                st.markdown(
                    "- Notes: "
                    f"`{notes_count}`\n"
                    "- Tools: "
                    f"`{tools_count}`\n"
                    "- Depth: "
                    f"`{payload.research_depth}`\n"
                    "- Max sources: "
                    f"`{payload.max_sources}`"
                )
        with c2:
            with st.container(border=True):
                st.markdown("**Writer**")
                st.markdown(
                    "- Words: "
                    f"`{_word_count(payload.draft)}`\n"
                    "- Type: "
                    f"`{payload.content_format}`\n"
                    "- Tone: "
                    f"`{payload.tone}`\n"
                    "- Length: "
                    f"`{payload.length_preference}`"
                )
        with c3:
            with st.container(border=True):
                st.markdown("**Editor**")
                st.markdown(
                    "- Revision loops: "
                    f"`{payload.revision_count}`\n"
                    "- Action items: "
                    f"`{feedback_count}`\n"
                    "- Strengths: "
                    f"`{strengths_count}`\n"
                    "- Weaknesses: "
                    f"`{weaknesses_count}`"
                )
        st.caption(
            "Revision loops count rewrite cycles only. "
            "Action items can still exist when loops are 0."
        )


def _render_lifecycle(st, payload: StatusPayload) -> None:
    if not payload.status_transitions:
        st.info("No lifecycle transitions captured yet.")
        return

    timeline_rows: list[dict[str, str]] = []
    for step in payload.status_transitions:
        timeline_rows.append(
            {
                "From": str(step.get("from") or "START"),
                "To": str(step.get("to") or payload.status),
                "At": str(step.get("at") or ""),
            }
        )
    st.table(timeline_rows)


def _render_research_section(st, payload: StatusPayload) -> None:
    with st.container(border=True):
        _render_section_header(st, "Research Tools")
        if payload.research_tools_used:
            st.write(" | ".join(payload.research_tools_used))
        else:
            st.write("No tools recorded for this run.")
    with st.container(border=True):
        _render_section_header(st, "Research Notes")
        if payload.research_notes:
            for note in payload.research_notes:
                st.write(f"- {note}")
        else:
            st.write("No research notes available yet.")


def _render_editorial_section(st, payload: StatusPayload) -> None:
    with st.container(border=True):
        _render_section_header(st, "Strengths")
        if payload.editor_strengths:
            for item in payload.editor_strengths:
                st.write(f"- {item}")
        else:
            st.write("No strengths captured yet.")
    with st.container(border=True):
        _render_section_header(st, "Weaknesses")
        if payload.editor_weaknesses:
            for item in payload.editor_weaknesses:
                st.write(f"- {item}")
        else:
            st.write("No weaknesses captured yet.")
    with st.container(border=True):
        _render_section_header(st, "Editor Action Items")
        if payload.editor_feedback:
            for item in payload.editor_feedback:
                st.write(f"- {item}")
        else:
            st.write(
                "No required actions. "
                "Draft may already satisfy criteria."
            )


def _render_lifecycle_section(st, payload: StatusPayload) -> None:
    with st.container(border=True):
        _render_section_header(st, "Lifecycle Timeline")
        _render_lifecycle(st, payload)


def _extract_citation_urls(payload: StatusPayload) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for note in payload.research_notes:
        for raw_url in _URL_PATTERN.findall(note):
            cleaned = raw_url.rstrip(".,);]")
            if cleaned in seen:
                continue
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _extract_citation_rows(
    payload: StatusPayload,
) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict[str, str]] = []

    for note in payload.research_notes:
        for block in _CITATION_BLOCK_PATTERN.findall(note):
            parsed = _parse_citation_block(block)
            key = (
                parsed["source"],
                parsed["url"],
                parsed["date"],
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "Source": parsed["source"],
                    "URL": parsed["url"],
                    "Date": parsed["date"],
                }
            )

    if rows:
        return rows

    for url in _extract_citation_urls(payload):
        parsed = urlparse(url)
        source = parsed.netloc or "unknown"
        key = (source, url, "unknown")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "Source": source,
                "URL": url,
                "Date": "unknown",
            }
        )
    return rows


def _parse_citation_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    parts = [part.strip() for part in block.split(";") if part.strip()]
    if parts and ":" not in parts[0]:
        fields["source"] = parts[0]
        parts = parts[1:]

    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", maxsplit=1)
        key_name = key.strip().lower()
        fields[key_name] = value.strip()
    return {
        "source": fields.get("source", "n/a"),
        "url": fields.get("url", "n/a"),
        "date": fields.get("date", "unknown"),
    }


def _render_citations_section(st, payload: StatusPayload) -> None:
    with st.container(border=True):
        _render_section_header(
            st,
            "Resources and Citations",
            "source links extracted from research notes",
        )
        citation_rows = _extract_citation_rows(payload)
        if citation_rows:
            st.table(citation_rows)
        else:
            st.write(
                "No citation metadata detected in research notes for "
                "this run."
            )
        tools_text = ", ".join(payload.research_tools_used) or "none"
        st.caption(f"Tools used for research: `{tools_text}`")


def _render_draft_section(st, payload: StatusPayload) -> None:
    _render_section_header(st, "Draft", "final generated output")
    if payload.draft:
        _render_copy_button(payload.draft)
        with st.container(border=True):
            st.markdown(payload.draft)
    else:
        st.info("Draft not available yet.")


def render_status_panel(
    st,
    payload: StatusPayload,
    *,
    view_key: str | None = None,
) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("Revision Loops", str(payload.revision_count))
    metric_cols[1].metric("Notes", str(len(payload.research_notes)))
    metric_cols[2].metric("Tools", str(len(payload.research_tools_used)))
    metric_cols[3].metric("Draft Words", str(_word_count(payload.draft)))

    with st.container(border=True):
        _render_section_header(st, "Run Profile")
        left_meta, right_meta = st.columns(2, gap="large")
        with left_meta:
            st.caption(f"Job ID: `{payload.job_id}`")
            st.caption(f"Created: {payload.created_at or 'n/a'}")
            st.caption(f"Last updated: {payload.updated_at}")
            st.caption(f"Status path: `{_status_path(payload)}`")
            st.caption(f"Mode: `{payload.llm_mode.upper()}`")
        with right_meta:
            tools_text = ", ".join(payload.research_tools_used) or "none"
            st.caption(f"Tools used: `{tools_text}`")
            st.caption(
                "Generation settings: "
                f"`type={payload.content_format}`, "
                f"`tone={payload.tone}`, "
                f"`length={payload.length_preference}`, "
                f"`depth={payload.research_depth}`, "
                f"`max_sources={payload.max_sources}`"
            )
            if payload.content_context:
                st.caption(f"Context: {payload.content_context}")

    panel_options = [
        "Overview",
        "Research",
        "Editorial",
        "Lifecycle",
        "Citations",
        "Draft",
    ]
    selector_key = view_key or f"execution-view-{payload.job_id}"
    st.markdown("#### Workspace")
    selected_panel = st.segmented_control(
        "Execution view",
        options=panel_options,
        key=selector_key,
        label_visibility="collapsed",
        selection_mode="single",
        width="stretch",
    )

    active_panel = selected_panel or "Overview"
    if active_panel == "Overview":
        _render_stage_summary(st, payload)
        if payload.content_context:
            with st.container(border=True):
                _render_section_header(st, "Context")
                st.write(payload.content_context)
    elif active_panel == "Research":
        _render_research_section(st, payload)
    elif active_panel == "Editorial":
        _render_editorial_section(st, payload)
    elif active_panel == "Lifecycle":
        _render_lifecycle_section(st, payload)
    elif active_panel == "Citations":
        _render_citations_section(st, payload)
    else:
        _render_draft_section(st, payload)


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
