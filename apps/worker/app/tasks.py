from __future__ import annotations

import re
import time

from apps.worker.app.celery_app import celery_app
from packages.core.constants import AgentStatus, LLMMode
from packages.core.errors import SafetyUnavailableError
from packages.core.job_store import get_job_store
from packages.core.safety import SafetyService
from packages.core.settings import Settings, get_settings
from packages.graph.agent_factory import build_agent_functions
from packages.graph.workflow import create_workflow

_OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")
_OPENAI_KEY_MESSAGE_PATTERN = re.compile(r"Incorrect API key provided:[^.]*\.")


@celery_app.task(name="worker.generate_blog")
def generate_blog_task(job_id: str) -> dict[str, str]:
    return process_job(job_id)


def process_job(job_id: str) -> dict[str, str]:
    store = get_job_store()
    base_settings = get_settings()
    safety = SafetyService(base_settings)

    record = store.get_job_or_raise(job_id)
    store.set_status(job_id=job_id, next_status=AgentStatus.RUNNING)

    try:
        settings = _settings_for_job(base_settings, record)
    except Exception as exc:
        store.set_status(
            job_id=job_id,
            next_status=AgentStatus.FAILED,
            error_message=_sanitize_error(str(exc)),
        )
        raise

    research_fn, writer_fn, editor_fn = build_agent_functions(settings)
    workflow = create_workflow(
        research_fn=research_fn,
        writer_fn=writer_fn,
        editor_fn=editor_fn,
    )

    max_attempts = settings.llm_max_retries
    if max_attempts < 1:
        max_attempts = 1

    attempt = 0
    while True:
        attempt += 1
        try:
            result = workflow.invoke(
                record,
                config={"configurable": {"thread_id": job_id}},
            )
            break
        except Exception as exc:
            if attempt >= max_attempts:
                store.set_status(
                    job_id=job_id,
                    next_status=AgentStatus.FAILED,
                    error_message=_sanitize_error(str(exc)),
                )
                raise

            store.set_status(
                job_id=job_id,
                next_status=AgentStatus.RETRYING,
                error_message=_sanitize_error(str(exc)),
            )
            delay = min(
                settings.llm_max_backoff_seconds,
                settings.llm_base_backoff_seconds * (2 ** (attempt - 1)),
            )
            time.sleep(delay)
            store.set_status(
                job_id=job_id,
                next_status=AgentStatus.RUNNING,
                error_message=None,
            )

    if not isinstance(result, dict):  # pragma: no cover
        store.set_status(
            job_id=job_id,
            next_status=AgentStatus.FAILED,
            error_message="Workflow returned non-dict state.",
        )
        raise RuntimeError("Workflow returned non-dict state.")

    final_status = AgentStatus(result["status"])
    if final_status == AgentStatus.COMPLETED:
        try:
            output_decision = safety.classify_output(
                str(result.get("draft", ""))
            )
        except SafetyUnavailableError:
            output_decision = None
            final_status = AgentStatus.ESCALATED
            result["status"] = final_status
            result["error_message"] = (
                "Output blocked: safety moderation service unavailable."
            )
            result["draft"] = ""
        else:
            if output_decision.blocked:
                final_status = AgentStatus.ESCALATED
                result["status"] = final_status
                result["error_message"] = output_decision.message
                result["draft"] = ""

        if final_status == AgentStatus.ESCALATED:
            result["is_approved"] = False
            feedback = list(result.get("editor_feedback", []))
            feedback.append(
                "Draft was escalated by safety guardrails "
                "and withheld from output."
            )
            result["editor_feedback"] = feedback

    store.set_status(job_id=job_id, next_status=final_status)

    updates = {key: value for key, value in result.items() if key != "status"}
    store.update_job(job_id=job_id, updates=updates)

    return {
        "job_id": job_id,
        "status": final_status.value,
    }


def _settings_for_job(
    base_settings: Settings,
    record: dict[str, object],
) -> Settings:
    raw_mode = str(record.get("llm_mode", LLMMode.MOCK.value)).lower()
    mode = LLMMode(raw_mode)

    if mode == LLMMode.OPENAI and not base_settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required when llm_mode is 'openai'."
        )
    if mode == LLMMode.OPENAI and base_settings.mock_mode_strict:
        raise ValueError(
            "OPENAI mode is disabled while MOCK_MODE_STRICT is true."
        )

    return base_settings.model_copy(
        update={"use_mock_llm": mode == LLMMode.MOCK}
    )


def _sanitize_error(message: str) -> str:
    cleaned = _OPENAI_KEY_PATTERN.sub("sk-REDACTED", message)
    cleaned = _OPENAI_KEY_MESSAGE_PATTERN.sub(
        "Incorrect API key provided: [REDACTED].",
        cleaned,
    )
    return cleaned
