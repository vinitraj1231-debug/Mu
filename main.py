from __future__ import annotations

import asyncio
import logging
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pyrogram import Client, idle

from musicbot.cache import RedisStore
from musicbot.config import settings
from musicbot.db import MongoStore
from musicbot.handlers import register_handlers
from musicbot.player import QueueManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("musicbot")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b"Bot is running"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_http_server() -> None:
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    log.info("HTTP keepalive server started on port %s", port)
    server.serve_forever()


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
    stop_event = asyncio.Event()

    def _shutdown(*_args):
        stop_event.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _shutdown)
            except NotImplementedError:
                pass
    except RuntimeError:
        pass

    threading.Thread(target=run_http_server, daemon=True).start()

    redis_store = RedisStore(settings.redis_url)
    mongo_store = MongoStore(settings.mongo_url, settings.mongo_db)

    await bot.start()
    await speaker.start()

    manager = QueueManager(redis_store, mongo_store, speaker)
    manager.start()

    register_handlers(bot, manager, redis_store, mongo_store)

    log.info("Bot started successfully")
    await idle()

    await stop_event.wait()

    await bot.stop()
    await speaker.stop()


if __name__ == "__main__":
    asyncio.run(main())
