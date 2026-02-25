from __future__ import annotations

import pytest

from packages.core.observability import _get_cached_observability
from packages.core.settings import get_settings


@pytest.fixture(autouse=True)
def _reset_runtime_settings(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    get_settings.cache_clear()
    _get_cached_observability.cache_clear()
    yield
    get_settings.cache_clear()
    _get_cached_observability.cache_clear()
