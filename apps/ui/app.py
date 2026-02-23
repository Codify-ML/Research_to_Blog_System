from __future__ import annotations

import time

import streamlit as st

from apps.ui.api_client import ApiClient, ApiClientError, StatusResult
from apps.ui.components.status_panel import (
    is_terminal_status,
    render_status_panel,
    terminal_message,
)
from apps.ui.settings import get_ui_settings


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


def _submit_topic(client: ApiClient, topic: str) -> None:
    result = client.generate(topic)
    st.session_state["active_job_id"] = result.job_id
    st.session_state["latest_status"] = None
    st.session_state["ui_error"] = None


def _fetch_status(client: ApiClient, job_id: str) -> StatusResult | None:
    try:
        payload = client.get_status(job_id)
    except ApiClientError as exc:
        st.session_state["ui_error"] = str(exc)
        return None

    st.session_state["latest_status"] = payload
    st.session_state["ui_error"] = None
    return payload


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
        submitted = st.form_submit_button("Generate Blog")

    if submitted:
        if not topic.strip():
            st.session_state["ui_error"] = "Topic cannot be blank."
        else:
            try:
                _submit_topic(client, topic.strip())
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

    should_refresh = st.button("Refresh Status")
    if should_refresh or latest_status is None:
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
