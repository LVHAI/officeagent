"""
Agent 调度器。

负责将 Supervisor 生成的任务分发给不同 Agent。
"""

import asyncio


class TaskScheduler:
    """简单任务调度器。"""

    def __init__(self):
        self.queue = asyncio.Queue()

    async def submit(self, task):
        """提交任务到队列。"""
        await self.queue.put(task)

    async def consume(self):
        """获取任务。

        后续可扩展 Worker Pool 和 Redis Queue。
        """
        return await self.queue.get()
