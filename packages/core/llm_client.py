from dataclasses import dataclass
from typing import Protocol

from packages.core.settings import Settings


class LLMClient(Protocol):
    def complete(self, *, prompt: str, model: str) -> str:
        """Return a completion string for the given prompt and model."""


@dataclass(slots=True)
class MockLLMClient:
    def complete(self, *, prompt: str, model: str) -> str:
        return (
            f"[MOCK:{model}] "
            f"Deterministic response for prompt hash length={len(prompt)}"
        )


@dataclass(slots=True)
class OpenAILLMClient:
    api_key: str

    def complete(self, *, prompt: str, model: str) -> str:
        # Phase 2 will replace this stub with real OpenAI API integration.
        raise NotImplementedError(
            "OpenAILLMClient is not wired yet. "
            "Enable USE_MOCK_LLM=true for now, or complete Phase 2 wiring."
        )


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.use_mock_llm:
        return MockLLMClient()
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required when USE_MOCK_LLM is false."
        )
    return OpenAILLMClient(api_key=settings.openai_api_key)
