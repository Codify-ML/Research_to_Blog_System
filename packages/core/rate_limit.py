from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

from packages.core.errors import RateLimitUnavailableError
from packages.core.settings import Settings

_GENERATE_WINDOW_SECONDS = 120
_STATUS_WINDOW_SECONDS = 120


@dataclass(slots=True)
class RateLimitDecision:
    blocked: bool
    code: str | None = None
    message: str = ""
    retry_after_seconds: int | None = None

    @classmethod
    def allow(cls) -> RateLimitDecision:
        return cls(
            blocked=False,
            code=None,
            message="",
            retry_after_seconds=None,
        )


def build_rate_limit_identity(*, api_key: str | None, client_ip: str) -> str:
    payload = f"{api_key or 'anonymous'}|{client_ip or 'unknown'}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RateLimitService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = redis.Redis.from_url(settings.redis_url)

    def check_generate(self, identity: str) -> RateLimitDecision:
        if not self.settings.rate_limit_enabled:
            return RateLimitDecision.allow()

        count = self._safe_counter_increment(
            key=self._minute_bucket_key("gen", identity),
            ttl_seconds=_GENERATE_WINDOW_SECONDS,
        )
        if count is None:
            return RateLimitDecision.allow()
        if count <= self.settings.rate_limit_generate_per_minute:
            return RateLimitDecision.allow()
        return RateLimitDecision(
            blocked=True,
            code="RATE_LIMITED",
            message="Too many generate requests. Try again shortly.",
            retry_after_seconds=_seconds_until_next_minute(),
        )

    def check_status(self, identity: str) -> RateLimitDecision:
        if not self.settings.rate_limit_enabled:
            return RateLimitDecision.allow()

        count = self._safe_counter_increment(
            key=self._minute_bucket_key("status", identity),
            ttl_seconds=_STATUS_WINDOW_SECONDS,
        )
        if count is None:
            return RateLimitDecision.allow()
        if count <= self.settings.rate_limit_status_per_minute:
            return RateLimitDecision.allow()
        return RateLimitDecision(
            blocked=True,
            code="RATE_LIMITED",
            message="Too many status requests. Try again shortly.",
            retry_after_seconds=_seconds_until_next_minute(),
        )

    def check_cooldown(self, identity: str) -> RateLimitDecision:
        if not self.settings.rate_limit_enabled:
            return RateLimitDecision.allow()

        key = self._cooldown_key(identity)
        ttl = self._safe_ttl(key)
        if ttl is None:
            return RateLimitDecision.allow()
        if ttl <= 0:
            return RateLimitDecision.allow()
        return RateLimitDecision(
            blocked=True,
            code="ABUSE_COOLDOWN",
            message=(
                "Input policy abuse cooldown is active. "
                "Please retry later."
            ),
            retry_after_seconds=ttl,
        )

    def record_policy_violation(self, identity: str) -> RateLimitDecision:
        if not self.settings.rate_limit_enabled:
            return RateLimitDecision.allow()

        count = self._safe_counter_increment(
            key=self._violation_key(identity),
            ttl_seconds=self.settings.abuse_window_seconds,
        )
        if count is None:
            return RateLimitDecision.allow()
        if count < self.settings.abuse_violation_threshold:
            return RateLimitDecision.allow()

        cooldown_key = self._cooldown_key(identity)
        if self._safe_set_with_expiry(
            key=cooldown_key,
            value="1",
            ttl_seconds=self.settings.abuse_cooldown_seconds,
        ):
            return RateLimitDecision(
                blocked=True,
                code="ABUSE_COOLDOWN",
                message=(
                    "Input policy abuse cooldown is active. "
                    "Please retry later."
                ),
                retry_after_seconds=self.settings.abuse_cooldown_seconds,
            )
        return RateLimitDecision.allow()

    def _minute_bucket_key(self, scope: str, identity: str) -> str:
        bucket = int(time.time() // 60)
        return f"rl:{scope}:{identity}:{bucket}"

    def _violation_key(self, identity: str) -> str:
        return f"abuse:viol:{identity}"

    def _cooldown_key(self, identity: str) -> str:
        return f"abuse:cool:{identity}"

    def _safe_counter_increment(
        self,
        *,
        key: str,
        ttl_seconds: int,
    ) -> int | None:
        try:
            value = int(self._client.incr(key))
            if value == 1:
                self._client.expire(key, ttl_seconds)
            return value
        except RedisError as exc:
            if self.settings.rate_limit_fail_open:
                return None
            raise RateLimitUnavailableError(
                "Rate limiting service unavailable."
            ) from exc

    def _safe_ttl(self, key: str) -> int | None:
        try:
            ttl = int(self._client.ttl(key))
            if ttl < 0:
                return 0
            return ttl
        except RedisError as exc:
            if self.settings.rate_limit_fail_open:
                return None
            raise RateLimitUnavailableError(
                "Rate limiting service unavailable."
            ) from exc

    def _safe_set_with_expiry(
        self,
        *,
        key: str,
        value: str,
        ttl_seconds: int,
    ) -> bool:
        try:
            self._client.set(key, value, ex=ttl_seconds)
            return True
        except RedisError as exc:
            if self.settings.rate_limit_fail_open:
                return False
            raise RateLimitUnavailableError(
                "Rate limiting service unavailable."
            ) from exc


def _seconds_until_next_minute() -> int:
    remainder = int(time.time()) % 60
    return max(1, 60 - remainder)
