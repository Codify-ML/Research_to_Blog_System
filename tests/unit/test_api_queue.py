from __future__ import annotations

from kombu.exceptions import OperationalError

from apps.api.app.queue import enqueue_generate_job
from packages.core.errors import QueueUnavailableError


def test_enqueue_generate_job_uses_fail_fast_publish(monkeypatch):
    captured: dict[str, object] = {}

    class _Result:
        id = "task-123"

    def _fake_apply_async(*, args, retry):
        captured["args"] = args
        captured["retry"] = retry
        return _Result()

    monkeypatch.setattr(
        "apps.api.app.queue.generate_blog_task.apply_async",
        _fake_apply_async,
    )

    task_id = enqueue_generate_job("job-abc")

    assert task_id == "task-123"
    assert captured["args"] == ["job-abc"]
    assert captured["retry"] is False


def test_enqueue_generate_job_raises_queue_unavailable(monkeypatch):
    def _raise_operational_error(*, args, retry):
        raise OperationalError("broker down")

    monkeypatch.setattr(
        "apps.api.app.queue.generate_blog_task.apply_async",
        _raise_operational_error,
    )

    try:
        enqueue_generate_job("job-abc")
    except QueueUnavailableError as exc:
        assert "Background queue is unavailable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected QueueUnavailableError.")
