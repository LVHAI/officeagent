from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


async def run_with_timeout(operation: Awaitable[T], timeout: float) -> T:
    """给异步操作设置硬超时，并将取消信号继续传递给下游任务。"""
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    task = asyncio.ensure_future(operation)
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int = 2,
    base_delay: float = 0.25,
    retryable: Callable[[Exception], bool] | None = None,
) -> T:
    """Retry transient async work without ever swallowing cancellation."""
    if retries < 0:
        raise ValueError("retries must be greater than or equal to zero")
    if base_delay < 0:
        raise ValueError("base_delay must be greater than or equal to zero")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await operation()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt >= retries or (retryable is not None and not retryable(exc)):
                raise
            delay = base_delay * (2**attempt)
            if delay:
                await asyncio.sleep(delay)
    raise RuntimeError("retry_async exhausted without a result") from last_error


async def gather_bounded(
    operations: Sequence[Awaitable[T]],
    limit: int,
) -> list[T | BaseException]:
    """限制并发任务数量，并保证外层取消时所有 Worker 都被回收。"""
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    semaphore = asyncio.Semaphore(limit)

    async def guarded(operation: Awaitable[T]) -> T:
        async with semaphore:
            return await operation

    tasks = [asyncio.ensure_future(guarded(operation)) for operation in operations]
    try:
        return await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
