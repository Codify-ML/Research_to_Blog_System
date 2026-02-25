from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from packages.core.settings import Settings, get_settings


class NoopObservability:
    @contextmanager
    def span(
        self,
        *,
        name: str,
        input_payload: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        del name
        del input_payload
        del metadata
        yield None

    def flush(self) -> None:
        return None


class LangfuseObservability:
    def __init__(
        self,
        *,
        client: Any,
        capture_content: bool,
    ) -> None:
        self._client = client
        self._capture_content = capture_content

    @contextmanager
    def span(
        self,
        *,
        name: str,
        input_payload: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        payload = input_payload if self._capture_content else None
        span_factory = getattr(self._client, "start_as_current_span", None)
        if callable(span_factory):
            kwargs = _clean_kwargs(
                {
                    "name": name,
                    "input": payload,
                    "metadata": metadata,
                }
            )
            with span_factory(**kwargs) as span:
                yield span
            return

        start_span = getattr(self._client, "start_span", None)
        if callable(start_span):
            kwargs = _clean_kwargs(
                {
                    "name": name,
                    "input": payload,
                    "metadata": metadata,
                }
            )
            span = start_span(**kwargs)
            try:
                yield span
            finally:
                _safe_end(span)
            return

        yield None

    def flush(self) -> None:
        flush_fn = getattr(self._client, "flush", None)
        if callable(flush_fn):
            flush_fn()


def update_span(
    span: Any,
    *,
    output_payload: Any | None = None,
    metadata: dict[str, Any] | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    if span is None:
        return

    update_fn = getattr(span, "update", None)
    if not callable(update_fn):
        return

    kwargs = _clean_kwargs(
        {
            "output": output_payload,
            "metadata": metadata,
            "level": level,
            "status_message": status_message,
        }
    )
    if kwargs:
        update_fn(**kwargs)


def _safe_end(span: Any) -> None:
    if span is None:
        return
    end_fn = getattr(span, "end", None)
    if callable(end_fn):
        end_fn()


def _clean_kwargs(raw_kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in raw_kwargs.items()
        if value is not None
    }


def _build_langfuse_client(settings: Settings) -> Any:
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        environment=settings.langfuse_environment,
        sample_rate=settings.langfuse_sample_rate,
    )


def _build_observability(
    settings: Settings,
) -> NoopObservability | LangfuseObservability:
    current_settings = settings
    if not current_settings.langfuse_enabled:
        return NoopObservability()

    try:
        client = _build_langfuse_client(current_settings)
    except Exception:
        return NoopObservability()

    return LangfuseObservability(
        client=client,
        capture_content=current_settings.langfuse_capture_content,
    )


@lru_cache(maxsize=1)
def _get_cached_observability() -> NoopObservability | LangfuseObservability:
    return _build_observability(get_settings())


def get_observability(
    settings: Settings | None = None,
) -> NoopObservability | LangfuseObservability:
    if settings is None:
        return _get_cached_observability()
    return _build_observability(settings)
