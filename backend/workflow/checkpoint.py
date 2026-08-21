"""
Workflow Checkpoint 管理。

用于保存 Agent 执行过程，支持异常恢复。

生产环境可以替换为 Redis / PostgreSQL / LangGraph Checkpointer。
"""

from typing import Dict, Any


class CheckpointManager:
    """简单 Checkpoint 存储实现。

    当前使用内存保存，主要用于定义接口。
    后续接入持久化存储。
    """

    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}

    async def save(self, checkpoint_id: str, state: Dict[str, Any]):
        """保存当前工作流状态。"""
        self._storage[checkpoint_id] = state

    async def load(self, checkpoint_id: str):
        """恢复工作流状态。"""
        return self._storage.get(checkpoint_id)
