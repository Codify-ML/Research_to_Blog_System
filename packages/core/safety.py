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
_LEETSPEAK_TRANSLATION_TABLE = str.maketrans(
    {
        "@": "a",
        "$": "s",
        "!": "i",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "0": "o",
    }
)
_HATE_CONTENT_TERMS = (
    "racist",
    "racism",
    "racial slur",
    "racial slurs",
    "supremacist",
    "white supremacy",
    "white power",
    "nazi",
    "neo nazi",
    "kkk",
    "ethnic cleansing",
    "lynching",
)
_PROMPT_INJECTION_PATTERNS = (
    re.compile(
        (
            r"\b(ignore|bypass|override|disable)\b.{0,40}"
            r"\b(safety|moderation|guardrail|policy)\b"
        ),
        re.IGNORECASE,
    ),
    re.compile(
        (
            r"\bignore\b.{0,20}\b(previous|prior|all)\b.{0,20}"
            r"\b(instruction|instructions|rule|rules)\b"
        ),
        re.IGNORECASE,
    ),
    re.compile(
        (
            r"\b(reveal|show|dump|print|expose|leak)\b.{0,50}"
            r"\b(system prompt|developer prompt|hidden prompt|api key|"
            r"password|secret|token|credential|credentials)\b"
        ),
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(jailbreak|dan mode|do anything now)\b",
        re.IGNORECASE,
    ),
)
_SENSITIVE_DATA_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        re.IGNORECASE,
    ),
    re.compile(
        (
            r"\b(api[_\s-]?key|password|secret|token)\b"
            r"\s*[:=]\s*[^\s]{8,}"
        ),
        re.IGNORECASE,
    ),
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
        if (
            self.settings.safety_hate_content_enabled
            and _contains_hate_content(candidate)
        ):
            reason_codes.append("SAFETY_HATE_CONTENT")
        if (
            self.settings.safety_prompt_injection_enabled
            and _contains_prompt_injection_or_exfiltration(candidate)
        ):
            reason_codes.append("SAFETY_PROMPT_INJECTION")
        if (
            self.settings.safety_sensitive_data_enabled
            and _contains_sensitive_data(candidate)
        ):
            reason_codes.append("SAFETY_SENSITIVE_DATA")

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
        score_codes = self._high_score_reason_codes(first)
        if score_codes:
            return score_codes
        if not first.flagged:
            return []

        raw = _categories_bool_map(getattr(first, "categories", None))

        reason_codes = [
            _category_to_reason_code(name)
            for name, enabled in raw.items()
            if enabled
        ]
        if reason_codes:
            return reason_codes
        return ["SAFETY_MODERATION_FLAGGED"]

    def _high_score_reason_codes(self, moderation_result: object) -> list[str]:
        raw_scores = _categories_float_map(
            getattr(moderation_result, "category_scores", None)
        )
        threshold = self.settings.safety_moderation_score_threshold
        return [
            _category_to_reason_code(name)
            for name, score in raw_scores.items()
            if score >= threshold
        ]


def _contains_profanity(text: str) -> bool:
    if profanity is not None:
        try:
            if profanity.contains_profanity(text):
                return True
        except Exception:  # pragma: no cover - defensive
            pass
    return bool(_FALLBACK_PROFANITY_PATTERN.search(text))


def _contains_hate_content(text: str) -> bool:
    normalized = _normalize_for_keyword_scan(text)
    if not normalized:
        return False

    compact = normalized.replace(" ", "")
    for term in _HATE_CONTENT_TERMS:
        term_normalized = term.lower().strip()
        if " " in term_normalized:
            if term_normalized in normalized:
                return True
            if term_normalized.replace(" ", "") in compact:
                return True
            continue
        if re.search(rf"\b{re.escape(term_normalized)}\b", normalized):
            return True
        if term_normalized in compact:
            return True

    return False


def _contains_prompt_injection_or_exfiltration(text: str) -> bool:
    normalized = _normalize_for_keyword_scan(text)
    if not normalized:
        return False
    return any(
        pattern.search(normalized)
        for pattern in _PROMPT_INJECTION_PATTERNS
    )


def _normalize_for_keyword_scan(text: str) -> str:
    normalized = text.lower().translate(_LEETSPEAK_TRANSLATION_TABLE)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_sensitive_data(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in _SENSITIVE_DATA_PATTERNS
    )


def _categories_bool_map(raw_categories: object) -> dict[str, bool]:
    raw = _dump_model_or_dict(raw_categories)
    return {
        str(key): bool(value)
        for key, value in raw.items()
    }


def _categories_float_map(raw_scores: object) -> dict[str, float]:
    raw = _dump_model_or_dict(raw_scores)
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        try:
            parsed[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return parsed


def _dump_model_or_dict(raw_object: object) -> dict[object, object]:
    if raw_object is None:
        return {}
    if hasattr(raw_object, "model_dump"):
        dumped = raw_object.model_dump()
        if isinstance(dumped, dict):
            return dumped
        return {}
    if isinstance(raw_object, dict):
        return raw_object
    return {}


def _category_to_reason_code(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not normalized:
        return "SAFETY_MODERATION_FLAGGED"
    return f"SAFETY_{normalized.upper()}"
