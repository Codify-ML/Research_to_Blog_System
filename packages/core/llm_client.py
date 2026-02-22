from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

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
        client = OpenAI(api_key=self.api_key)
        response = client.responses.create(
            model=model,
            input=prompt,
        )

        output_text = getattr(response, "output_text", "")
        if output_text:
            return output_text.strip()

        # Fallback for SDK response variants with nested content.
        try:
            chunks: list[str] = []
            for item in response.output:  # type: ignore[attr-defined]
                for content in item.content:
                    text = getattr(content, "text", None)
                    if text:
                        chunks.append(text)
            return "\n".join(chunks).strip()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI response did not contain parsable text output."
            ) from exc


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.use_mock_llm:
        return MockLLMClient()
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required when USE_MOCK_LLM is false."
        )
    return OpenAILLMClient(api_key=settings.openai_api_key)
