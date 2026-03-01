from contextlib import contextmanager

import pytest
from pydantic import ValidationError

from packages.core.llm_client import (
    MockLLMClient,
    OpenAILLMClient,
    get_llm_client,
)
from packages.core.settings import Settings


def test_settings_default_to_mock_mode() -> None:
    settings = Settings()
    assert settings.use_mock_llm is True


def test_settings_require_openai_key_when_mock_disabled() -> None:
    with pytest.raises(ValidationError):
        Settings(use_mock_llm=False, openai_api_key=None)


def test_settings_reject_strict_mock_with_real_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(
            use_mock_llm=False,
            mock_mode_strict=True,
            openai_api_key="test-key",
        )


def test_get_llm_client_returns_mock_client() -> None:
    settings = Settings(use_mock_llm=True, mock_mode_strict=True)
    client = get_llm_client(settings)
    assert isinstance(client, MockLLMClient)


def test_get_llm_client_returns_openai_client() -> None:
    settings = Settings(use_mock_llm=False, openai_api_key="test-key")
    client = get_llm_client(settings)
    assert isinstance(client, OpenAILLMClient)


def test_mock_client_is_deterministic() -> None:
    client = MockLLMClient()
    response = client.complete(prompt="hello", model="gpt-4.1-mini")
    assert response.startswith("[MOCK:gpt-4.1-mini]")


def test_web_search_tool_fallback_variant() -> None:
    client = OpenAILLMClient(api_key="test-key")
    tools = [
        {"type": "web_search"},
        {"type": "function", "name": "x", "parameters": {"type": "object"}},
    ]
    fallback = client._fallback_web_search_tools(tools)
    assert fallback is not None
    assert fallback[0]["type"] == "web_search_preview"


def test_mock_client_emits_observability_when_enabled() -> None:
    class _FakeSpan:
        def __init__(self) -> None:
            self.updates = []

        def update(self, **kwargs) -> None:
            self.updates.append(kwargs)

    class _FakeObs:
        def __init__(self) -> None:
            self.recorded_span = _FakeSpan()

        @contextmanager
        def span(self, **_kwargs):
            yield self.recorded_span

    obs = _FakeObs()
    client = MockLLMClient(observability=obs, capture_content=True)
    output = client.complete(prompt="hello", model="gpt-4.1-mini")
    assert output.startswith("[MOCK:gpt-4.1-mini]")
    assert obs.recorded_span.updates
    first_update = obs.recorded_span.updates[0]
    assert "output" in first_update
    assert first_update["output"]["output"] == output
