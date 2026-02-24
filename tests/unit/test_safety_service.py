from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.core.errors import SafetyUnavailableError
from packages.core.safety import SafetyService
from packages.core.settings import Settings


def test_profanity_prefilter_blocks_input() -> None:
    settings = Settings(
        use_mock_llm=True,
        safety_openai_moderation_enabled=False,
    )
    service = SafetyService(settings)

    decision = service.classify_input("This is fucking unacceptable.")

    assert decision.blocked is True
    assert "SAFETY_PROFANITY" in decision.reason_codes


def test_clean_text_allows_when_moderation_disabled() -> None:
    settings = Settings(
        use_mock_llm=True,
        safety_openai_moderation_enabled=False,
    )
    service = SafetyService(settings)

    decision = service.classify_input("Discuss roadmap planning basics.")

    assert decision.blocked is False
    assert decision.reason_codes == []


@dataclass(slots=True)
class _FakeCategories:
    hate: bool = False
    violence: bool = False

    def model_dump(self) -> dict[str, bool]:
        return {"hate": self.hate, "violence": self.violence}


@dataclass(slots=True)
class _FakeModerationResult:
    flagged: bool
    categories: _FakeCategories


@dataclass(slots=True)
class _FakeModerationResponse:
    results: list[_FakeModerationResult]


class _FakeModerations:
    def __init__(self, response: _FakeModerationResponse) -> None:
        self._response = response

    def create(self, **_kwargs):
        return self._response


class _FakeOpenAIClient:
    def __init__(self, response: _FakeModerationResponse) -> None:
        self.moderations = _FakeModerations(response)


def test_moderation_flag_adds_reason_codes() -> None:
    settings = Settings(
        use_mock_llm=True,
        openai_api_key="test-key",
        safety_openai_moderation_enabled=True,
    )
    service = SafetyService(settings)
    service._moderation_client = _FakeOpenAIClient(
        _FakeModerationResponse(
            results=[
                _FakeModerationResult(
                    flagged=True,
                    categories=_FakeCategories(hate=True),
                )
            ]
        )
    )

    decision = service.classify_input("safe words")

    assert decision.blocked is True
    assert "SAFETY_HATE" in decision.reason_codes


def test_fail_closed_raises_when_moderation_unavailable() -> None:
    settings = Settings(
        use_mock_llm=True,
        openai_api_key="test-key",
        safety_openai_moderation_enabled=True,
        safety_fail_closed=True,
    )
    service = SafetyService(settings)

    class _BrokenClient:
        class _Moderations:
            @staticmethod
            def create(**_kwargs):
                raise RuntimeError("unavailable")

        moderations = _Moderations()

    service._moderation_client = _BrokenClient()

    with pytest.raises(SafetyUnavailableError):
        service.classify_input("safe words")


def test_fail_closed_raises_when_key_missing_for_moderation() -> None:
    settings = Settings(
        use_mock_llm=True,
        openai_api_key=None,
        safety_openai_moderation_enabled=True,
        safety_fail_closed=True,
    )
    service = SafetyService(settings)

    with pytest.raises(SafetyUnavailableError):
        service.classify_input("Discuss project roadmap")
