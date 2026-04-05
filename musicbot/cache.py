from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


class RedisStore:
    def __init__(self, url: str) -> None:
        self.client = redis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        return await self.client.ping()

    async def get_json(self, key: str) -> dict[str, Any] | None:
        raw = await self.client.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: dict[str, Any], ttl: int = 3600) -> None:
        await self.client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    async def queue_get(self, chat_id: int) -> list[str]:
        key = f"queue:{chat_id}"
        return await self.client.lrange(key, 0, -1)

    async def queue_push(self, chat_id: int, *items: str) -> int:
        key = f"queue:{chat_id}"
        return await self.client.rpush(key, *items)

    async def queue_pop(self, chat_id: int) -> str | None:
        key = f"queue:{chat_id}"
        return await self.client.lpop(key)

    async def queue_clear(self, chat_id: int) -> None:
        await self.client.delete(f"queue:{chat_id}")

    async def set_current(self, chat_id: int, value: dict[str, Any]) -> None:
        await self.set_json(f"current:{chat_id}", value, ttl=24 * 3600)

    async def get_current(self, chat_id: int) -> dict[str, Any] | None:
        return await self.get_json(f"current:{chat_id}")

    async def clear_current(self, chat_id: int) -> None:
        await self.client.delete(f"current:{chat_id}")

    async def set_lock(self, chat_id: int, value: str = "1", ttl: int = 10) -> bool:
        return bool(await self.client.set(f"lock:{chat_id}", value, nx=True, ex=ttl))

    async def release_lock(self, chat_id: int) -> None:
        await self.client.delete(f"lock:{chat_id}")
