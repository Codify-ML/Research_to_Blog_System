from __future__ import annotations

import json
import time

import streamlit as st
import streamlit.components.v1 as components

try:
    from packages.core.constants import LLMMode
except ModuleNotFoundError:  # pragma: no cover - script-mode fallback
    from enum import StrEnum

    class LLMMode(StrEnum):
        MOCK = "mock"
        OPENAI = "openai"


try:
    from apps.ui.api_client import ApiClient, ApiClientError
    from apps.ui.components.status_panel import (
        is_terminal_status,
        render_status_panel,
        terminal_message,
    )
    from apps.ui.settings import get_ui_settings
except ModuleNotFoundError:  # pragma: no cover - script-mode fallback
    from api_client import ApiClient, ApiClientError
    from components.status_panel import (
        is_terminal_status,
        render_status_panel,
        terminal_message,
    )
    from settings import get_ui_settings


def _build_client() -> ApiClient:
    settings = get_ui_settings()
    return ApiClient(
        base_url=settings.ui_api_base_url,
        timeout_seconds=settings.ui_request_timeout_seconds,
    )


def _init_session_state() -> None:
    if "active_job_id" not in st.session_state:
        st.session_state["active_job_id"] = None
    if "latest_status" not in st.session_state:
        st.session_state["latest_status"] = None
    if "ui_error" not in st.session_state:
        st.session_state["ui_error"] = None
    if "active_llm_mode" not in st.session_state:
        st.session_state["active_llm_mode"] = LLMMode.MOCK.value
    if "active_generation_options" not in st.session_state:
        st.session_state["active_generation_options"] = {}


def _submit_topic(
    client: ApiClient,
    *,
    topic: str,
    llm_mode: LLMMode,
    max_sources: int,
    content_format: str,
    content_context: str,
    tone: str,
    length_preference: str,
    research_depth: str,
) -> None:
    result = client.generate(
        topic=topic,
        llm_mode=llm_mode.value,
        max_sources=max_sources,
        content_format=content_format,
        content_context=content_context,
        tone=tone,
        length_preference=length_preference,
        research_depth=research_depth,
    )
    st.session_state["active_job_id"] = result.job_id
    st.session_state["active_llm_mode"] = result.llm_mode
    st.session_state["active_generation_options"] = {
        "max_sources": max_sources,
        "content_format": content_format,
        "tone": tone,
        "length_preference": length_preference,
        "research_depth": research_depth,
    }
    st.session_state["latest_status"] = None
    st.session_state["ui_error"] = None


def _clear_active_run() -> None:
    st.session_state["active_job_id"] = None
    st.session_state["latest_status"] = None
    st.session_state["ui_error"] = None
    st.session_state["active_generation_options"] = {}
    st.session_state["active_llm_mode"] = LLMMode.MOCK.value


def _fetch_status(client: ApiClient, job_id: str):
    try:
        payload = client.get_status(job_id)
    except ApiClientError as exc:
        st.session_state["ui_error"] = str(exc)
        return None

    st.session_state["latest_status"] = payload
    st.session_state["active_generation_options"] = {
        "max_sources": payload.max_sources,
        "content_format": payload.content_format,
        "tone": payload.tone,
        "length_preference": payload.length_preference,
        "research_depth": payload.research_depth,
    }
    st.session_state["ui_error"] = None
    return payload


def _render_copy_job_id_button(job_id: str) -> None:
    job_id_json = json.dumps(job_id)
    components.html(
        f"""
        <button onclick='copyJobId()'
        style="padding:6px 12px;border-radius:6px;border:1px solid #bbb;">
          Copy Job ID
        </button>
        <span id="copy-job-id-msg"
        style="margin-left:8px;font-size:0.9em;"></span>
        <script>
        async function copyJobId() {{
          const msg = document.getElementById("copy-job-id-msg");
          try {{
            await navigator.clipboard.writeText({job_id_json});
            msg.textContent = "Copied.";
          }} catch (err) {{
            msg.textContent = "Copy failed. Copy manually.";
          }}
        }}
        </script>
        """,
        height=45,
    )


def main() -> None:
    settings = get_ui_settings()
    client = _build_client()

    st.set_page_config(page_title="Research to Blog UI", layout="wide")
    st.title("Research to Blog - Phase 3 UI")
    st.caption(f"Connected API: `{settings.ui_api_base_url}`")

    _init_session_state()

    with st.form("submit-topic-form"):
        topic = st.text_input(
            "Topic",
            placeholder="Example: Multi-agent workflows in production",
        )
        selected_label = st.radio(
            "LLM Mode",
            options=("Mock LLM", "OpenAI LLM"),
            index=0,
            horizontal=True,
        )
        with st.expander("Advanced Controls"):
            max_sources = st.slider(
                "Max Web Sources",
                min_value=1,
                max_value=20,
                value=6,
                step=1,
            )
            content_format = st.text_input(
                "Content Type",
                value="Blog article",
                help="Examples: LinkedIn post, magazine article, newsletter.",
            )
            content_context = st.text_area(
                "Content Context",
                value="",
                height=80,
                help=("Optional audience/use-case context to guide writing."),
            )
            tone = st.selectbox(
                "Tone",
                options=[
                    "professional",
                    "humorous",
                    "conversational",
                    "technical",
                    "persuasive",
                ],
                index=0,
            )
            length_preference = st.selectbox(
                "Length",
                options=["short", "balanced", "long"],
                index=1,
            )
            research_depth = st.selectbox(
                "Research Depth",
                options=["light", "standard", "deep"],
                index=1,
                help="Controls how broad/deep the research notes should be.",
            )
        submitted = st.form_submit_button("Generate Blog")

    if submitted:
        if not topic.strip():
            st.session_state["ui_error"] = "Topic cannot be blank."
        else:
            _clear_active_run()
            selected_mode = (
                LLMMode.MOCK
                if selected_label == "Mock LLM"
                else LLMMode.OPENAI
            )
            try:
                _submit_topic(
                    client,
                    topic=topic.strip(),
                    llm_mode=selected_mode,
                    max_sources=max_sources,
                    content_format=content_format.strip() or "Blog article",
                    content_context=content_context.strip(),
                    tone=tone,
                    length_preference=length_preference,
                    research_depth=research_depth,
                )
                st.success("Job submitted successfully.")
            except ApiClientError as exc:
                st.session_state["ui_error"] = str(exc)

    job_id = st.session_state["active_job_id"]
    latest_status = st.session_state["latest_status"]

    if st.session_state["ui_error"]:
        st.error(st.session_state["ui_error"])

    if not job_id:
        st.info("Submit a topic to start a job.")
        return

    st.subheader("Execution")
    st.write(f"Tracking job: `{job_id}`")
    _render_copy_job_id_button(job_id)
    st.caption(
        "Selected mode: "
        f"`{str(st.session_state['active_llm_mode']).upper()}`"
    )
    options = st.session_state["active_generation_options"]
    if options:
        st.caption(
            "Options: "
            f"`max_sources={options.get('max_sources', 6)}`, "
            f"`type={options.get('content_format', 'Blog article')}`, "
            f"`tone={options.get('tone', 'professional')}`, "
            f"`length={options.get('length_preference', 'balanced')}`, "
            f"`depth={options.get('research_depth', 'standard')}`"
        )

    should_refresh = st.button("Refresh Status")
    should_auto_poll = latest_status is None or not is_terminal_status(
        latest_status.status
    )
    if should_refresh or should_auto_poll:
        latest_status = _fetch_status(client, job_id)

    if latest_status is None:
        return

    render_status_panel(st, latest_status)

    if is_terminal_status(latest_status.status):
        if latest_status.status == "COMPLETED":
            st.success(terminal_message(latest_status))
        else:
            st.error(terminal_message(latest_status))
        return

    st.info(
        "Job is still running. Auto-refreshing status shortly "
        f"(every {settings.ui_poll_interval_seconds:.1f}s)."
    )
    time.sleep(settings.ui_poll_interval_seconds)
    st.rerun()


if __name__ == "__main__":
    main()
