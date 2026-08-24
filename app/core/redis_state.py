from __future__ import annotations

import logging

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisTaskCoordinator:
    """Best-effort Redis coordination for short-lived task state."""

    def __init__(self, client: Redis, ttl_seconds: int = 3600) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(task_id: str) -> str:
        return f"officeagent:task:{task_id}"

    async def set_status(self, task_id: str, status: str) -> None:
        await self.client.set(self.key(task_id), status, ex=self.ttl_seconds)

    async def get_status(self, task_id: str) -> str | None:
        value = await self.client.get(self.key(task_id))
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else str(value)

    async def delete(self, task_id: str) -> None:
        await self.client.delete(self.key(task_id))


_redis_client: Redis | None = None
_coordinator: RedisTaskCoordinator | None = None


def get_redis_task_coordinator() -> RedisTaskCoordinator:
    global _redis_client, _coordinator
    if _coordinator is None:
        _redis_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=False,
        )
        _coordinator = RedisTaskCoordinator(_redis_client)
    return _coordinator


async def close_redis_task_coordinator() -> None:
    global _redis_client, _coordinator
    if _redis_client is not None:
        await _redis_client.aclose()
    _redis_client = None
    _coordinator = None
