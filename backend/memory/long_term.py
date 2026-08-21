"""
长期记忆模块。

用于保存跨任务、跨会话的高价值信息，例如用户偏好、历史分析经验等。
实际生产环境可以接入 Milvus、pgvector 等向量数据库。
"""

from typing import List
from .models import MemoryItem


class LongTermMemory:
    """长期记忆管理。

    这里只定义统一接口，避免 Agent 直接依赖具体数据库。
    """

    def __init__(self, storage):
        self.storage = storage

    async def save(self, memory: MemoryItem):
        """保存长期记忆。"""
        return await self.storage.save(memory)

    async def search(self, query: str) -> List[MemoryItem]:
        """根据语义查询历史记忆。"""
        return await self.storage.query(query)
