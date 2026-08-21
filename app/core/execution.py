from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

T = TypeVar("T")


async def run_with_timeout(operation: Awaitable[T], timeout: float) -> T:
    """给异步操作设置硬超时，并将取消信号继续传递给下游任务。"""
    return await asyncio.wait_for(operation, timeout=timeout)


async def gather_bounded(
    operations: list[Awaitable[T]],
    limit: int,
) -> list[T | BaseException]:
    """限制并发任务数量，避免 Agent 数量增长后瞬间打满模型或 MCP 服务。"""
    semaphore = asyncio.Semaphore(max(1, limit))

    async def guarded(operation: Awaitable[T]) -> T:
        async with semaphore:
            return await operation

    return await asyncio.gather(*(guarded(operation) for operation in operations), return_exceptions=True)
