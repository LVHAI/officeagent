"""
短期记忆管理。

保存当前 Agent 执行过程中的上下文信息，
用于 Workflow 中断恢复。
"""

from typing import Dict, Any


class ShortTermMemory:
    def __init__(self):
        # 当前版本使用内存实现，生产环境替换为 Redis
        self._storage: Dict[str, Dict[str, Any]] = {}

    async def save_context(self, task_id: str, context: Dict[str, Any]):
        self._storage[task_id] = context

    async def get_context(self, task_id: str):
        return self._storage.get(task_id)

    async def delete_context(self, task_id: str):
        self._storage.pop(task_id, None)
