from __future__ import annotations

import json

from redis.asyncio import Redis

from app.core.config import Settings, settings


class RedisCache:
    def __init__(self, current: Settings = settings) -> None:
        self.client = Redis(host=current.redis_host, port=current.redis_port, decode_responses=True)

    async def get_json(self, key: str) -> dict | None:
        value = await self.client.get(key)
        return json.loads(value) if value else None

    async def set_json(self, key: str, value: dict, ttl_seconds: int = 300) -> None:
        await self.client.set(key, json.dumps(value), ex=ttl_seconds)

    async def close(self) -> None:
        await self.client.aclose()
