from __future__ import annotations

from contextlib import contextmanager

from packages.core.observability import (
    LangfuseObservability,
    NoopObservability,
    _get_cached_observability,
    get_observability,
    update_span,
)
from packages.core.settings import Settings


def test_get_observability_returns_noop_when_disabled() -> None:
    settings = Settings(
        use_mock_llm=True,
        langfuse_enabled=False,
    )
    _get_cached_observability.cache_clear()

    obs = get_observability(settings)

    assert isinstance(obs, NoopObservability)
    with obs.span(name="test") as span:
        assert span is None


def test_get_observability_returns_langfuse_when_enabled(monkeypatch) -> None:
    class _FakeSpan:
        def __init__(self) -> None:
            self.updated = []

        def update(self, **kwargs) -> None:
            self.updated.append(kwargs)

    class _FakeClient:
        @contextmanager
        def start_as_current_span(self, **_kwargs):
            yield _FakeSpan()

    def _fake_builder(_settings: Settings):
        return _FakeClient()

    settings = Settings(
        use_mock_llm=True,
        langfuse_enabled=True,
        langfuse_public_key="pk",
        langfuse_secret_key="sk",
        langfuse_host="http://127.0.0.1:3000",
    )
    _get_cached_observability.cache_clear()
    monkeypatch.setattr(
        "packages.core.observability._build_langfuse_client",
        _fake_builder,
    )

    obs = get_observability(settings)

    assert isinstance(obs, LangfuseObservability)
    with obs.span(name="test", metadata={"k": "v"}) as span:
        update_span(span, metadata={"m": "1"})
        assert span is not None
