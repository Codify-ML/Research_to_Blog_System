from __future__ import annotations

from kombu.exceptions import OperationalError

from apps.worker.app.tasks import generate_blog_task
from packages.core.errors import QueueUnavailableError


def enqueue_generate_job(job_id: str) -> str:
    try:
        task_result = generate_blog_task.apply_async(
            args=[job_id],
            retry=False,
        )
    except OperationalError as exc:
        raise QueueUnavailableError("Background queue is unavailable") from exc
    return str(task_result.id)
