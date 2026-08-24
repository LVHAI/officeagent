from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    retries: int = 3,
    base_delay: float = 0.25,
) -> T:
    """异步重试：使用指数退避，避免瞬时故障导致请求立即连续打满下游服务。"""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt == retries:
                raise
            # 第一次等待 base_delay，之后按 2^attempt 增长，降低重试风暴风险。
            await asyncio.sleep(base_delay * (2**attempt))
    raise last_error or RuntimeError("retry failed")
