from __future__ import annotations

import json
from html import escape

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
        status_level,
        terminal_message,
    )
    from apps.ui.settings import get_ui_settings
except ModuleNotFoundError:  # pragma: no cover - script-mode fallback
    from api_client import ApiClient, ApiClientError
    from components.status_panel import (
        is_terminal_status,
        render_status_panel,
        status_level,
        terminal_message,
    )
    from settings import get_ui_settings


def _build_client() -> ApiClient:
    settings = get_ui_settings()
    return ApiClient(
        base_url=settings.ui_api_base_url,
        timeout_seconds=settings.ui_request_timeout_seconds,
        api_auth_enabled=settings.api_auth_enabled,
        api_auth_key=settings.api_auth_key,
    )


def _inject_ui_styles() -> None:
    st.markdown(
        """
        <style>
        .rtb-section-h {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 0.5rem;
          margin-bottom: 0.35rem;
          padding-bottom: 0.3rem;
          border-bottom: 1px solid var(--secondary-background-color);
        }
        .rtb-title {
          font-weight: 700;
          color: var(--text-color);
          letter-spacing: 0.1px;
        }
        .rtb-sub {
          color: var(--text-color);
          opacity: 0.72;
          font-size: 0.82rem;
        }
        div[data-testid="stSidebarContent"] {
          border-right: 1px solid var(--secondary-background-color);
          padding-right: 0.3rem;
        }
        div[data-testid="stSidebarContent"] label,
        div[data-testid="stSidebarContent"] p,
        div[data-testid="stSidebarContent"] span {
          color: var(--text-color) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_signout_url() -> str | None:
    settings = get_ui_settings()
    if (
        not settings.ui_cognito_hosted_ui_base
        or not settings.ui_cognito_client_id
    ):
        return None

    public_base = settings.ui_public_base_url.rstrip("/")
    return f"{public_base}/auth/logout"


def _classify_ui_error(
    *,
    error_message: str,
    error_code: str | None,
    blocked_category: str | None = None,
    reason_codes: list[str] | None = None,
    safety_signals: list[str] | None = None,
) -> tuple[str, str]:
    if error_code == "POLICY_BLOCKED_INPUT":
        category_guidance = {
            "profanity": (
                "Input includes profanity or abusive language. "
                "Use neutral, professional wording."
            ),
            "hate_content": (
                "Input includes hateful or discriminatory language. "
                "Use respectful, non-discriminatory wording."
            ),
            "prompt_injection": (
                "Input looks like an instruction-bypass attempt. "
                "Focus on the blog topic only."
            ),
            "sensitive_data": (
                "Input appears to include sensitive data (keys/passwords). "
                "Remove secrets and personal data."
            ),
            "moderation": (
                "Input triggered moderation safeguards. "
                "Revise the prompt to be safer and more neutral."
            ),
        }
        category_text = category_guidance.get(
            (blocked_category or "").lower(),
            "Request blocked by safety policy.",
        )
        reasons_text = ""
        if reason_codes:
            reasons_text = (
                "\n\nSignals: " + ", ".join(sorted(set(reason_codes)))
            )
        evidence_text = ""
        if safety_signals:
            evidence_text = (
                "\n\nMatched terms/patterns: "
                + ", ".join(safety_signals)
            )
        return (
            "warning",
            f"{category_text}\n\n"
            "Please revise your prompt and try again."
            f"{reasons_text}{evidence_text}\n\n"
            f"Details: {error_message}",
        )
    if error_code == "SAFETY_UNAVAILABLE":
        return (
            "error",
            "Safety checks are temporarily unavailable. "
            "Please retry shortly.",
        )
    return ("error", error_message)


def _render_navigation_button(*, label: str, url: str) -> None:
    safe_label = escape(label)
    safe_url = escape(url, quote=True)
    st.markdown(
        (
            f'<a href="{safe_url}" target="_self" '
            'style="text-decoration:none;">'
            '<div style="padding:0.45rem 0.75rem;'
            "border-radius:0.5rem;border:1px solid #d9d9d9;"
            "background:#f8f8f8;cursor:pointer;text-align:center;"
            f'font-weight:600;">{safe_label}</div></a>'
        ),
        unsafe_allow_html=True,
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
    if "sidebar_topic" not in st.session_state:
        st.session_state["sidebar_topic"] = ""
    if "sidebar_show_advanced_controls" not in st.session_state:
        st.session_state["sidebar_show_advanced_controls"] = False
    if "collapse_advanced_controls_next_run" not in st.session_state:
        st.session_state["collapse_advanced_controls_next_run"] = False
    if "sidebar_max_sources" not in st.session_state:
        st.session_state["sidebar_max_sources"] = 6
    if "sidebar_content_type" not in st.session_state:
        st.session_state["sidebar_content_type"] = "Blog Post"
    if "sidebar_content_context" not in st.session_state:
        st.session_state["sidebar_content_context"] = ""
    if "sidebar_tone" not in st.session_state:
        st.session_state["sidebar_tone"] = "professional"
    if "sidebar_length" not in st.session_state:
        st.session_state["sidebar_length"] = "balanced"
    if "sidebar_research_depth" not in st.session_state:
        st.session_state["sidebar_research_depth"] = "standard"


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
    st.session_state.pop("execution_view_last_job", None)
    st.session_state.pop("execution_view_last_terminal", None)


def _fetch_status(client: ApiClient, job_id: str):
    try:
        payload = client.get_status(job_id)
    except ApiClientError as exc:
        st.session_state["ui_error"] = {
            "message": str(exc),
            "code": exc.error_code,
            "blocked_category": exc.blocked_category,
            "reason_codes": exc.reason_codes,
            "safety_signals": exc.safety_signals,
        }
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


def _render_sidebar_run_status(
    *,
    job_id: str | None,
    latest_status,
) -> None:
    st.markdown("### Run Status")
    if not job_id:
        st.caption("No active job yet.")
        return

    st.caption(f"Tracking: `{job_id}`")
    if latest_status is None:
        st.info("Queued or starting. Waiting for first status update.")
        return

    level = status_level(latest_status.status)
    status_line = f"Status: {latest_status.status}"
    getattr(st, level)(status_line)
    if is_terminal_status(latest_status.status):
        terminal = terminal_message(latest_status)
        if latest_status.status == "COMPLETED":
            st.success(terminal)
        else:
            st.error(terminal)
    else:
        st.caption("Auto-refresh is active.")


def _render_execution_panel(
    *,
    client: ApiClient,
    settings,
    job_id: str,
) -> None:
    latest_status = st.session_state.get("latest_status")

    st.subheader("Execution")
    run_header_col, refresh_col = st.columns([8.2, 1.4])
    with run_header_col:
        st.write(f"Tracking job: `{job_id}`")
        _render_copy_job_id_button(job_id)
    with refresh_col:
        should_refresh = st.button(
            "Refresh Status",
            key=f"refresh-status-{job_id}",
        )

    should_auto_poll = latest_status is None or not is_terminal_status(
        latest_status.status
    )
    if should_refresh or should_auto_poll:
        latest_status = _fetch_status(client, job_id)

    if latest_status is None:
        return

    current_terminal = is_terminal_status(latest_status.status)
    desired_view = "Draft" if current_terminal else "Lifecycle"
    view_key = f"execution-view-{job_id}"
    last_job = st.session_state.get("execution_view_last_job")
    last_terminal = st.session_state.get("execution_view_last_terminal")
    if (
        last_job != job_id or last_terminal is None
        or bool(last_terminal) != current_terminal
    ):
        st.session_state[view_key] = desired_view
    st.session_state["execution_view_last_job"] = job_id
    st.session_state["execution_view_last_terminal"] = current_terminal

    render_status_panel(
        st,
        latest_status,
        view_key=view_key,
    )


def _render_sidebar_status_panel() -> None:
    current_job_id = st.session_state.get("active_job_id")
    latest_status = st.session_state.get("latest_status")
    _render_sidebar_run_status(
        job_id=current_job_id,
        latest_status=latest_status,
    )


def main() -> None:
    settings = get_ui_settings()
    client = _build_client()

    st.set_page_config(page_title="Research-to-Blog Studio", layout="wide")
    _inject_ui_styles()

    _init_session_state()
    if st.session_state.pop("collapse_advanced_controls_next_run", False):
        st.session_state["sidebar_show_advanced_controls"] = False

    with st.sidebar:
        st.title("Research-to-Blog Studio")
        st.caption("From web-grounded notes to publish-ready drafts")
        sign_out_url = _build_signout_url()
        if sign_out_url is not None:
            _render_navigation_button(
                label="Sign Out",
                url=sign_out_url,
            )
        st.caption(f"Connected API: `{settings.ui_api_base_url}`")
        st.markdown("---")
        st.markdown("### Controls")
        raw_topic = str(st.session_state.get("sidebar_topic", ""))
        wrapped_lines = max(
            raw_topic.count("\n") + 1,
            len(raw_topic) // 54 + 1,
        )
        topic_height = min(220, max(72, wrapped_lines * 24))
        st.toggle(
            "Show Advanced Controls",
            key="sidebar_show_advanced_controls",
        )
        with st.form("submit-topic-form"):
            topic = st.text_area(
                "Topic",
                placeholder="Example: Multi-agent workflows in production",
                key="sidebar_topic",
                height=topic_height,
            )
            selected_label = st.radio(
                "LLM Mode",
                options=("Mock LLM", "OpenAI LLM"),
                index=0,
                horizontal=True,
                key="sidebar_llm_mode",
            )
            if st.session_state["sidebar_show_advanced_controls"]:
                max_sources = st.slider(
                    "Max Web Sources",
                    min_value=1,
                    max_value=20,
                    value=6,
                    step=1,
                    key="sidebar_max_sources",
                )
                content_format = st.text_input(
                    "Content Type",
                    help=(
                        "Examples: LinkedIn post, "
                        "magazine article, newsletter."
                    ),
                    key="sidebar_content_type",
                    label_visibility="visible",
                    value="Blog Post",
                )
                content_context = st.text_area(
                    "Content Context",
                    height=80,
                    help=(
                        "Optional audience/use-case context to "
                        "guide writing."
                    ),
                    key="sidebar_content_context",
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
                    key="sidebar_tone",
                )
                length_preference = st.selectbox(
                    "Length",
                    options=["short", "balanced", "long"],
                    index=1,
                    key="sidebar_length",
                )
                research_depth = st.selectbox(
                    "Research Depth",
                    options=["light", "standard", "deep"],
                    index=1,
                    help=(
                        "Controls how broad/deep the research "
                        "notes should be."
                    ),
                    key="sidebar_research_depth",
                )
            else:
                max_sources = int(
                    st.session_state.get("sidebar_max_sources", 6)
                )
                content_format = str(
                    st.session_state.get(
                        "sidebar_content_type",
                        "Blog Post",
                    )
                )
                content_context = str(
                    st.session_state.get("sidebar_content_context", "")
                )
                tone = str(
                    st.session_state.get("sidebar_tone", "professional")
                )
                length_preference = str(
                    st.session_state.get("sidebar_length", "balanced")
                )
                research_depth = str(
                    st.session_state.get(
                        "sidebar_research_depth",
                        "standard",
                    )
                )
            submitted = st.form_submit_button("Generate Blog")

    if submitted:
        st.session_state["collapse_advanced_controls_next_run"] = True
        if not topic.strip():
            st.session_state["ui_error"] = {
                "message": "Topic cannot be blank.",
                "code": "LOCAL_VALIDATION",
            }
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
                    content_format=content_format.strip() or "Blog Post",
                    content_context=content_context.strip(),
                    tone=tone,
                    length_preference=length_preference,
                    research_depth=research_depth,
                )
            except ApiClientError as exc:
                st.session_state["ui_error"] = {
                    "message": str(exc),
                    "code": exc.error_code,
                    "blocked_category": exc.blocked_category,
                    "reason_codes": exc.reason_codes,
                    "safety_signals": exc.safety_signals,
                }
        st.rerun()

    job_id = st.session_state["active_job_id"]

    ui_error = st.session_state["ui_error"]
    if ui_error:
        if isinstance(ui_error, dict):
            level, rendered = _classify_ui_error(
                error_message=str(ui_error.get("message", "Unknown error.")),
                error_code=(
                    str(ui_error["code"])
                    if ui_error.get("code") is not None
                    else None
                ),
                blocked_category=(
                    str(ui_error["blocked_category"])
                    if ui_error.get("blocked_category") is not None
                    else None
                ),
                reason_codes=(
                    [
                        str(item)
                        for item in ui_error["reason_codes"]
                    ]
                    if isinstance(ui_error.get("reason_codes"), list)
                    else None
                ),
                safety_signals=(
                    [
                        str(item)
                        for item in ui_error["safety_signals"]
                    ]
                    if isinstance(
                        ui_error.get("safety_signals"),
                        list,
                    )
                    else None
                ),
            )
        else:
            level, rendered = _classify_ui_error(
                error_message=str(ui_error),
                error_code=None,
            )

        if level == "warning":
            st.warning(rendered)
        else:
            st.error(rendered)

    with st.sidebar:
        sidebar_fragment = st.fragment(
            run_every=settings.ui_poll_interval_seconds
        )(_render_sidebar_status_panel)
        sidebar_fragment()

    if not job_id:
        st.info("Submit a topic to start a job.")
        return

    execution_fragment = st.fragment(
        run_every=settings.ui_poll_interval_seconds
    )(_render_execution_panel)
    execution_fragment(
        client=client,
        settings=settings,
        job_id=job_id,
    )


if __name__ == "__main__":
    main()
