from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Sequence
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
        # 外部取消必须继续取消底层 Task，避免 Agent/MCP 请求成为孤儿任务。
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise


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
        # Supervisor / API 取消任务时，不能遗留等待 Semaphore 或 MCP 的后台 Worker。
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
