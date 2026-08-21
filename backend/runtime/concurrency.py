"""
并发任务执行基础模块。

用于 Multi-Agent 并行执行场景:
- Knowledge Agent
- Tool Agent
- Web Agent

后续可扩展 Worker Pool 和任务队列。
"""

import asyncio
from typing import Awaitable, List, Any


async def execute_parallel(tasks: List[Awaitable]) -> List[Any]:
    """并行执行多个 Agent 任务。

    使用 asyncio.gather 提升多 Agent 场景执行效率。
    return_exceptions=True 保证单个 Agent 失败不会影响其他任务。
    """

    return await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )
