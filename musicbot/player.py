from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pyrogram import Client
from pytgcalls import PyTgCalls

from .cache import RedisStore
from .db import MongoStore
from .yt import Track


class QueueManager:
    def __init__(self, redis_store: RedisStore, mongo: MongoStore, speaker: Client) -> None:
        self.redis = redis_store
        self.mongo = mongo
        self.speaker = speaker
        self.call = PyTgCalls(self.speaker)
        self.current_tasks: dict[int, asyncio.Task] = {}
        self.local_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def start(self) -> None:
        self.call.start()

    async def ensure_joined(self, chat_id: int) -> None:
        # play() implicitly joins in many pytgcalls builds; keeping a dedicated hook here
        return None

    async def enqueue(self, chat_id: int, track: Track) -> int:
        await self.redis.queue_push(chat_id, __import__("json").dumps(asdict(track), ensure_ascii=False))
        await self.mongo.increment_stat("requests")
        await self.mongo.add_history(
            {
                "chat_id": chat_id,
                "title": track.title,
                "webpage_url": track.webpage_url,
                "requester": track.requester,
                "created_at": datetime.now(timezone.utc),
            }
        )
        return len(await self.redis.queue_get(chat_id))

    async def play_next(self, chat_id: int) -> None:
        async with self.local_locks[chat_id]:
            current = await self.redis.get_current(chat_id)
            if current and current.get("is_playing"):
                return

            raw = await self.redis.queue_pop(chat_id)
            if not raw:
                await self.redis.clear_current(chat_id)
                return

            import json
            payload = json.loads(raw)
            await self.redis.set_current(chat_id, {**payload, "is_playing": True, "started_at": datetime.now(timezone.utc).isoformat()})
            await self._start_stream(chat_id, payload)

    async def _start_stream(self, chat_id: int, payload: dict) -> None:
        stream_url = payload["stream_url"]

        # Start playback
        self.call.play(chat_id, stream_url)

        # watchdog for autoplay next
        duration = int(payload.get("duration") or 0)
        task = self.current_tasks.get(chat_id)
        if task:
            task.cancel()

        async def _watch() -> None:
            try:
                # small guard to reduce race conditions with skip/stop
                wait_for = max(duration, 0)
                if wait_for <= 0:
                    wait_for = 60 * 60 * 24
                await asyncio.sleep(wait_for)
                await self._finish_and_continue(chat_id)
            except asyncio.CancelledError:
                return

        self.current_tasks[chat_id] = asyncio.create_task(_watch())

    async def _finish_and_continue(self, chat_id: int) -> None:
        await self.redis.clear_current(chat_id)
        await self.play_next(chat_id)

    async def skip(self, chat_id: int) -> None:
        with contextlib.suppress(Exception):
            self.call.stop(chat_id)
        task = self.current_tasks.pop(chat_id, None)
        if task:
            task.cancel()
        await self.redis.clear_current(chat_id)
        await self.play_next(chat_id)

    async def stop(self, chat_id: int) -> None:
        with contextlib.suppress(Exception):
            self.call.stop(chat_id)
        task = self.current_tasks.pop(chat_id, None)
        if task:
            task.cancel()
        await self.redis.clear_current(chat_id)
        await self.redis.queue_clear(chat_id)

    async def pause(self, chat_id: int) -> None:
        # Depending on installed PyTgCalls version, pause may be implemented differently.
        # We keep a safe fallback.
        for method_name in ("pause", "pause_stream"):
            method = getattr(self.call, method_name, None)
            if callable(method):
                result = method(chat_id)
                if asyncio.iscoroutine(result):
                    await result
                return
        raise RuntimeError("Pause method not available in this PyTgCalls build")

    async def resume(self, chat_id: int) -> None:
        for method_name in ("resume", "resume_stream"):
            method = getattr(self.call, method_name, None)
            if callable(method):
                result = method(chat_id)
                if asyncio.iscoroutine(result):
                    await result
                return
        raise RuntimeError("Resume method not available in this PyTgCalls build")

    async def volume(self, chat_id: int, level: int) -> None:
        method = getattr(self.call, "set_volume", None) or getattr(self.call, "volume", None)
        if not callable(method):
            raise RuntimeError("Volume method not available in this PyTgCalls build")
        result = method(chat_id, level)
        if asyncio.iscoroutine(result):
            await result

    async def current_queue(self, chat_id: int) -> list[dict]:
        raw_items = await self.redis.queue_get(chat_id)
        import json
        return [json.loads(i) for i in raw_items]

    async def now_playing(self, chat_id: int) -> dict | None:
        return await self.redis.get_current(chat_id)
