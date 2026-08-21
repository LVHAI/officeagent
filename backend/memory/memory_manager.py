"""
Memory Manager 统一管理 Agent 记忆。

Agent 不直接依赖具体存储，通过该层解耦。
"""


class MemoryManager:
    def __init__(self, storage=None):
        self.storage = storage

    async def save_memory(self, memory):
        if self.storage:
            await self.storage.save(memory)

    async def search_memory(self, user_id: str, keyword: str):
        if self.storage:
            return await self.storage.query(user_id, keyword)
        return []

    async def remove_memory(self, memory_id: str):
        if self.storage:
            await self.storage.delete(memory_id)
