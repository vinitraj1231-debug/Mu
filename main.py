from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, idle

from musicbot.cache import RedisStore
from musicbot.config import settings
from musicbot.db import MongoStore
from musicbot.handlers import register_handlers
from musicbot.player import QueueManager


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("musicbot")


bot = Client(
    "musicbot-controller",
    api_id=settings.api_id,
    api_hash=settings.api_hash,
    bot_token=settings.bot_token,
    in_memory=True,
)

speaker = Client(
    "musicbot-speaker",
    api_id=settings.api_id,
    api_hash=settings.api_hash,
    session_string=settings.session_string,
    in_memory=True,
)


async def main() -> None:
    redis_store = RedisStore(settings.redis_url)
    mongo_store = MongoStore(settings.mongo_url, settings.mongo_db)

    await bot.start()
    await speaker.start()

    manager = QueueManager(redis_store, mongo_store, speaker)
    manager.start()

    register_handlers(bot, manager, redis_store, mongo_store)

    log.info("Bot started")
    await idle()

    await bot.stop()
    await speaker.stop()


if __name__ == "__main__":
    asyncio.run(main())
