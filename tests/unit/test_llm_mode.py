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
