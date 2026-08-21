from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """下游连续失败后暂时停止请求。"""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failures = 0
        self.opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.recovery_seconds:
            self.opened_at = None
            self.failures = 0
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.2,
    breaker: CircuitBreaker | None = None,
) -> T:
    """指数退避重试；CancelledError 永远不重试，避免吞掉上游取消。"""
    if attempts <= 0:
        raise ValueError("attempts must be positive")
    for attempt in range(attempts):
        if breaker is not None and not breaker.allow():
            raise CircuitOpenError("downstream circuit is open")
        try:
            result = await operation()
            if breaker is not None:
                breaker.success()
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            if breaker is not None:
                breaker.failure()
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (2**attempt))
    raise AssertionError("unreachable")
