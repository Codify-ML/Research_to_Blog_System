from __future__ import annotations

import re
import time

from apps.worker.app.celery_app import celery_app
from packages.core.constants import AgentStatus
from packages.core.job_store import get_job_store
from packages.core.settings import get_settings
from packages.graph.agent_factory import build_agent_functions
from packages.graph.workflow import create_workflow

_OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")
_OPENAI_KEY_MESSAGE_PATTERN = re.compile(r"Incorrect API key provided:[^.]*\.")


@celery_app.task(name="worker.generate_blog")
def generate_blog_task(job_id: str) -> dict[str, str]:
    return process_job(job_id)


def process_job(job_id: str) -> dict[str, str]:
    store = get_job_store()
    settings = get_settings()

    record = store.get_job_or_raise(job_id)
    store.set_status(job_id=job_id, next_status=AgentStatus.RUNNING)

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
    store.set_status(job_id=job_id, next_status=final_status)

    updates = {key: value for key, value in result.items() if key != "status"}
    store.update_job(job_id=job_id, updates=updates)

    return {
        "job_id": job_id,
        "status": final_status.value,
    }


def _sanitize_error(message: str) -> str:
    cleaned = _OPENAI_KEY_PATTERN.sub("sk-REDACTED", message)
    cleaned = _OPENAI_KEY_MESSAGE_PATTERN.sub(
        "Incorrect API key provided: [REDACTED].",
        cleaned,
    )
    return cleaned
