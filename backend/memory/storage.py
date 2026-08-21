"""
记忆存储抽象层。

后续可以接入 Redis、PostgreSQL、Milvus 等真实存储。
"""

from abc import ABC, abstractmethod
from typing import List

from .models import MemoryItem


class MemoryStorage(ABC):
    """所有记忆存储实现需要遵循的接口。"""

    @abstractmethod
    async def save(self, item: MemoryItem) -> None:
        pass

    @abstractmethod
    async def query(self, user_id: str, keyword: str) -> List[MemoryItem]:
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> None:
        pass
