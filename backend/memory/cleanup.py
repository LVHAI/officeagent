"""
记忆清理策略。

避免长期运行后 Vector Memory 出现垃圾数据积累。
支持：
1. TTL 过期清理
2. 低价值记忆淘汰
3. 后续扩展相似度去重
"""

from datetime import datetime


class MemoryCleanup:
    def __init__(self, storage):
        self.storage = storage

    async def cleanup_expired(self):
        """删除已经超过生命周期的记忆。"""
        return await self.storage.delete_expired(datetime.now())

    async def remove_low_value(self, threshold: float = 0.2):
        """清理低重要性的历史记忆。"""
        return await self.storage.delete_by_score(threshold)
