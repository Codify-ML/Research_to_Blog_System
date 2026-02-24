from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.2,
    max_delay_seconds: float = 2.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Execute fn with bounded exponential backoff and jitter."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except retry_on:
            if attempt >= max_attempts:
                raise
            delay = min(
                max_delay_seconds,
                base_delay_seconds * (2 ** (attempt - 1)),
            )
            delay += random.uniform(0.0, base_delay_seconds)
            time.sleep(delay)
