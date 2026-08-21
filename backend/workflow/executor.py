"""
Workflow 执行器。

负责：
1. 调度 Agent 节点执行。
2. 控制并发执行。
3. 隔离单个 Agent 异常，避免影响整个任务。
"""

import asyncio
from typing import Callable, Dict

from .state import AgentState


class WorkflowExecutor:
    """Agent 工作流执行器。"""

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_node(self, name: str, handler: Callable, state: AgentState):
        """执行单个 Agent 节点。

        使用 semaphore 限制并发数量，避免大量任务耗尽资源。
        """
        async with self.semaphore:
            try:
                return await handler(state)
            except Exception as exc:
                # 单节点失败只记录错误，不影响其它 Agent。
                state.errors.append({"node": name, "error": str(exc)})
                return state

    async def execute_parallel(self, nodes: Dict[str, Callable], state: AgentState):
        """并行执行多个 Agent 节点。"""
        tasks = [self.execute_node(name, fn, state) for name, fn in nodes.items()]
        await asyncio.gather(*tasks)
        return state
