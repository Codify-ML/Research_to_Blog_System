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
    signals: list[str] = field(default_factory=list)
    message: str = ""

    @classmethod
    def allow(cls) -> SafetyDecision:
        return cls(
            blocked=False,
            reason_codes=[],
            signals=[],
            message="",
        )

    @classmethod
    def block(
        cls,
        *,
        reason_codes: list[str],
        signals: list[str] | None,
        prefix: str,
    ) -> SafetyDecision:
        sorted_codes = sorted(set(reason_codes))
        ordered_signals = _dedupe_preserve_order(signals or [])
        return cls(
            blocked=True,
            reason_codes=sorted_codes,
            signals=ordered_signals,
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
        signals: list[str] = []

        profanity_signals = _profanity_signals(candidate)
        if self.settings.safety_profanity_enabled and profanity_signals:
            reason_codes.append("SAFETY_PROFANITY")
            signals.extend(
                f"profanity:{signal}"
                for signal in profanity_signals
            )
        hate_signals = _hate_content_signals(candidate)
        if (
            self.settings.safety_hate_content_enabled
            and hate_signals
        ):
            reason_codes.append("SAFETY_HATE_CONTENT")
            signals.extend(
                f"hate:{signal}"
                for signal in hate_signals
            )
        prompt_injection_signals = (
            _prompt_injection_or_exfiltration_signals(candidate)
        )
        if (
            self.settings.safety_prompt_injection_enabled
            and prompt_injection_signals
        ):
            reason_codes.append("SAFETY_PROMPT_INJECTION")
            signals.extend(
                f"prompt_injection:{signal}"
                for signal in prompt_injection_signals
            )
        sensitive_data_signals = _sensitive_data_signals(candidate)
        if (
            self.settings.safety_sensitive_data_enabled
            and sensitive_data_signals
        ):
            reason_codes.append("SAFETY_SENSITIVE_DATA")
            signals.extend(
                f"sensitive_data:{signal}"
                for signal in sensitive_data_signals
            )

        moderation_codes = self._moderation_reason_codes(candidate)
        reason_codes.extend(moderation_codes)
        signals.extend(
            f"moderation:{code.lower()}"
            for code in moderation_codes
        )
        if reason_codes:
            return SafetyDecision.block(
                reason_codes=reason_codes,
                signals=signals,
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
    return bool(_profanity_signals(text))


def _profanity_signals(text: str) -> list[str]:
    signals: list[str] = []
    normalized_tokens = _normalize_for_keyword_scan(text).split()
    token_set = set(normalized_tokens)

    if profanity is not None:
        try:
            if profanity.contains_profanity(text):
                censor_words = getattr(
                    profanity,
                    "CENSOR_WORDSET",
                    set(),
                )
                censor_word_set = {
                    str(word).lower().strip()
                    for word in censor_words
                    if str(word).strip()
                }
                # Avoid substring false positives (e.g. "intuit"):
                # only accept exact token intersections.
                signals.extend(
                    sorted(token_set.intersection(censor_word_set))
                )
        except Exception:  # pragma: no cover - defensive
            pass

    signals.extend(
        match.group(1).lower().strip()
        for match in _FALLBACK_PROFANITY_PATTERN.finditer(text)
    )
    return _dedupe_preserve_order(signals)


def _contains_hate_content(text: str) -> bool:
    return bool(_hate_content_signals(text))


def _hate_content_signals(text: str) -> list[str]:
    normalized = _normalize_for_keyword_scan(text)
    if not normalized:
        return []

    compact = normalized.replace(" ", "")
    matches: list[str] = []
    for term in _HATE_CONTENT_TERMS:
        term_normalized = term.lower().strip()
        if " " in term_normalized:
            if term_normalized in normalized:
                matches.append(term_normalized)
            if term_normalized.replace(" ", "") in compact:
                matches.append(term_normalized)
            continue
        if re.search(rf"\b{re.escape(term_normalized)}\b", normalized):
            matches.append(term_normalized)
        if term_normalized in compact:
            matches.append(term_normalized)

    return _dedupe_preserve_order(matches)


def _contains_prompt_injection_or_exfiltration(text: str) -> bool:
    return bool(_prompt_injection_or_exfiltration_signals(text))


def _prompt_injection_or_exfiltration_signals(text: str) -> list[str]:
    normalized = _normalize_for_keyword_scan(text)
    if not normalized:
        return []
    matches = [
        pattern.pattern
        for pattern in _PROMPT_INJECTION_PATTERNS
        if pattern.search(normalized)
    ]
    return _dedupe_preserve_order(matches)


def _normalize_for_keyword_scan(text: str) -> str:
    normalized = text.lower().translate(_LEETSPEAK_TRANSLATION_TABLE)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_sensitive_data(text: str) -> bool:
    return bool(_sensitive_data_signals(text))


def _sensitive_data_signals(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in _SENSITIVE_DATA_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return _dedupe_preserve_order(matches)


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


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered
