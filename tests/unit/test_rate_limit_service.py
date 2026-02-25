from __future__ import annotations

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from packages.core.errors import RateLimitUnavailableError
from packages.core.rate_limit import RateLimitService
from packages.core.settings import Settings


class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, int | str] = {}
        self._ttls: dict[str, int] = {}

    def incr(self, key: str) -> int:
        current = int(self._values.get(key, 0))
        current += 1
        self._values[key] = current
        return current

    def expire(self, key: str, ttl_seconds: int) -> bool:
        self._ttls[key] = ttl_seconds
        return True

    def ttl(self, key: str) -> int:
        if key not in self._values:
            return -2
        return self._ttls.get(key, -1)

    def set(self, key: str, value: str, ex: int) -> bool:
        self._values[key] = value
        self._ttls[key] = ex
        return True


class _BrokenRedis:
    def incr(self, _key: str) -> int:
        raise RedisConnectionError("redis unavailable")

    def expire(self, _key: str, _ttl_seconds: int) -> bool:
        raise RedisConnectionError("redis unavailable")

    def ttl(self, _key: str) -> int:
        raise RedisConnectionError("redis unavailable")

    def set(self, _key: str, _value: str, ex: int) -> bool:
        raise RedisConnectionError("redis unavailable")


def _service(**overrides) -> RateLimitService:
    settings = Settings(
        use_mock_llm=True,
        safety_openai_moderation_enabled=False,
        **overrides,
    )
    service = RateLimitService(settings)
    service._client = _FakeRedis()
    return service


def test_generate_limit_blocks_after_threshold() -> None:
    service = _service(rate_limit_generate_per_minute=2)
    identity = "id-1"

    first = service.check_generate(identity)
    second = service.check_generate(identity)
    third = service.check_generate(identity)

    assert first.blocked is False
    assert second.blocked is False
    assert third.blocked is True
    assert third.code == "RATE_LIMITED"
    assert third.retry_after_seconds is not None


def test_status_limit_blocks_after_threshold() -> None:
    service = _service(rate_limit_status_per_minute=1)
    identity = "id-2"

    first = service.check_status(identity)
    second = service.check_status(identity)

    assert first.blocked is False
    assert second.blocked is True
    assert second.code == "RATE_LIMITED"


def test_abuse_cooldown_is_triggered_at_threshold() -> None:
    service = _service(
        abuse_violation_threshold=2,
        abuse_cooldown_seconds=777,
    )
    identity = "id-3"

    first = service.record_policy_violation(identity)
    second = service.record_policy_violation(identity)
    cooldown = service.check_cooldown(identity)

    assert first.blocked is False
    assert second.blocked is True
    assert second.code == "ABUSE_COOLDOWN"
    assert second.retry_after_seconds == 777
    assert cooldown.blocked is True
    assert cooldown.code == "ABUSE_COOLDOWN"


def test_fail_open_allows_when_redis_unavailable() -> None:
    settings = Settings(
        use_mock_llm=True,
        safety_openai_moderation_enabled=False,
        rate_limit_enabled=True,
        rate_limit_fail_open=True,
    )
    service = RateLimitService(settings)
    service._client = _BrokenRedis()

    decision = service.check_generate("id-4")

    assert decision.blocked is False


def test_fail_closed_raises_when_redis_unavailable() -> None:
    settings = Settings(
        use_mock_llm=True,
        safety_openai_moderation_enabled=False,
        rate_limit_enabled=True,
        rate_limit_fail_open=False,
    )
    service = RateLimitService(settings)
    service._client = _BrokenRedis()

    with pytest.raises(RateLimitUnavailableError):
        service.check_generate("id-5")
