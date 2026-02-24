from __future__ import annotations

import re
from dataclasses import dataclass, field

from openai import OpenAI

from packages.core.errors import SafetyUnavailableError
from packages.core.settings import Settings

try:  # pragma: no cover - optional fallback
    from better_profanity import profanity
except ImportError:  # pragma: no cover - fallback path
    profanity = None

_FALLBACK_PROFANITY_PATTERN = re.compile(
    r"\b(fuck|fucking|shit|bitch|asshole)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class SafetyDecision:
    blocked: bool
    reason_codes: list[str] = field(default_factory=list)
    message: str = ""

    @classmethod
    def allow(cls) -> SafetyDecision:
        return cls(blocked=False, reason_codes=[], message="")

    @classmethod
    def block(
        cls,
        *,
        reason_codes: list[str],
        prefix: str,
    ) -> SafetyDecision:
        sorted_codes = sorted(set(reason_codes))
        return cls(
            blocked=True,
            reason_codes=sorted_codes,
            message=f"{prefix}: {', '.join(sorted_codes)}.",
        )


class SafetyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._moderation_client: OpenAI | None = None

        if profanity is not None:
            profanity.load_censor_words()

        if settings.openai_api_key:
            self._moderation_client = OpenAI(api_key=settings.openai_api_key)

    def classify_input(self, text: str) -> SafetyDecision:
        return self._classify(
            text=text,
            policy_prefix="Input blocked by safety policy",
        )

    def classify_output(self, text: str) -> SafetyDecision:
        return self._classify(
            text=text,
            policy_prefix="Output blocked by safety policy",
        )

    def _classify(self, *, text: str, policy_prefix: str) -> SafetyDecision:
        if not self.settings.safety_enabled:
            return SafetyDecision.allow()

        candidate = text.strip()
        if not candidate:
            return SafetyDecision.allow()

        reason_codes: list[str] = []
        if self.settings.safety_profanity_enabled and _contains_profanity(
            candidate
        ):
            reason_codes.append("SAFETY_PROFANITY")

        reason_codes.extend(self._moderation_reason_codes(candidate))
        if reason_codes:
            return SafetyDecision.block(
                reason_codes=reason_codes,
                prefix=policy_prefix,
            )
        return SafetyDecision.allow()

    def _moderation_reason_codes(self, text: str) -> list[str]:
        if not self.settings.safety_openai_moderation_enabled:
            return []
        if self._moderation_client is None:
            if self.settings.safety_fail_closed:
                raise SafetyUnavailableError(
                    "Safety moderation service unavailable."
                )
            return []

        try:
            response = self._moderation_client.moderations.create(
                model=self.settings.safety_openai_moderation_model,
                input=text,
            )
        except Exception as exc:
            if self.settings.safety_fail_closed:
                raise SafetyUnavailableError(
                    "Safety moderation service unavailable."
                ) from exc
            return []

        if not response.results:
            return []

        first = response.results[0]
        if not first.flagged:
            return []

        categories = getattr(first, "categories", None)
        raw: dict[str, bool] = {}
        if categories is not None:
            if hasattr(categories, "model_dump"):
                dumped = categories.model_dump()
                if isinstance(dumped, dict):
                    raw = {
                        str(key): bool(value)
                        for key, value in dumped.items()
                    }
            elif isinstance(categories, dict):
                raw = {
                    str(key): bool(value)
                    for key, value in categories.items()
                }

        reason_codes = [
            _category_to_reason_code(name)
            for name, enabled in raw.items()
            if enabled
        ]
        if reason_codes:
            return reason_codes
        return ["SAFETY_MODERATION_FLAGGED"]


def _contains_profanity(text: str) -> bool:
    if profanity is not None:
        try:
            if profanity.contains_profanity(text):
                return True
        except Exception:  # pragma: no cover - defensive
            pass
    return bool(_FALLBACK_PROFANITY_PATTERN.search(text))


def _category_to_reason_code(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not normalized:
        return "SAFETY_MODERATION_FLAGGED"
    return f"SAFETY_{normalized.upper()}"
