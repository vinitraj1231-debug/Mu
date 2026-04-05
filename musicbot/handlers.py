from __future__ import annotations

from pyrogram import filters
from pyrogram.types import Message

from .config import settings
from .player import QueueManager
from .yt import resolve_track


def register_handlers(bot, manager: QueueManager, redis_store, mongo_store):
    @bot.on_message(filters.command("start"))
    async def start(_, msg: Message):
        await msg.reply_text(
            "Fast music bot is online. Use /play in a group voice-chat enabled chat."
        )

    @bot.on_message(filters.command("ping"))
    async def ping(_, msg: Message):
        await msg.reply_text("pong")

    @bot.on_message(filters.command("play"))
    async def play(_, msg: Message):
        if len(msg.command) < 2 and not msg.reply_to_message:
            await msg.reply_text("Use: /play song name or reply to an audio/video message.")
            return

        query = None
        if msg.reply_to_message and msg.reply_to_message.audio:
            query = msg.reply_to_message.audio.file_id
        elif msg.reply_to_message and msg.reply_to_message.video:
            query = msg.reply_to_message.video.file_id
        else:
            query = msg.text.split(maxsplit=1)[1]

        await msg.reply_text("Resolving track...")
        track = await resolve_track(
            query,
            requester=msg.from_user.mention if msg.from_user else "anonymous",
            cache_get=redis_store.get_json,
            cache_set=redis_store.set_json,
        )

        await manager.enqueue(msg.chat.id, track)
        await msg.reply_text(f"Queued: {track.title}")
        await manager.play_next(msg.chat.id)

    @bot.on_message(filters.command("skip"))
    async def skip(_, msg: Message):
        await manager.skip(msg.chat.id)
        await msg.reply_text("Skipped.")

    @bot.on_message(filters.command("stop"))
    async def stop(_, msg: Message):
        await manager.stop(msg.chat.id)
        await msg.reply_text("Stopped and cleared queue.")

    @bot.on_message(filters.command("pause"))
    async def pause(_, msg: Message):
        try:
            await manager.pause(msg.chat.id)
            await msg.reply_text("Paused.")
        except Exception as e:
            await msg.reply_text(f"Pause failed: {e}")

    @bot.on_message(filters.command("resume"))
    async def resume(_, msg: Message):
        try:
            await manager.resume(msg.chat.id)
            await msg.reply_text("Resumed.")
        except Exception as e:
            await msg.reply_text(f"Resume failed: {e}")

    @bot.on_message(filters.command("volume"))
    async def volume(_, msg: Message):
        if len(msg.command) < 2:
            await msg.reply_text("Use: /volume 1-200")
            return
        level = int(msg.command[1])
        await manager.volume(msg.chat.id, level)
        await msg.reply_text(f"Volume set to {level}")

    @bot.on_message(filters.command("queue"))
    async def queue(_, msg: Message):
        items = await manager.current_queue(msg.chat.id)
        current = await manager.now_playing(msg.chat.id)
        text = []
        if current:
            text.append(f"Now playing: {current.get('title')}")
        else:
            text.append("Now playing: nothing")
        if items:
            text.append("")
            text.append("Queue:")
            for i, item in enumerate(items[:20], start=1):
                text.append(f"{i}. {item['title']}")
        else:
            text.append("")
            text.append("Queue is empty.")
        await msg.reply_text("\n".join(text))

    @bot.on_message(filters.command("clearcache"))
    async def clearcache(_, msg: Message):
        await redis_store.client.flushdb()
        await msg.reply_text("Redis cache cleared.")

    @bot.on_message(filters.command("history"))
    async def history(_, msg: Message):
        docs = await mongo_store.get_top_queries(10)
        if not docs:
            await msg.reply_text("No history yet.")
            return
        text = ["Recent history:"]
        for d in docs:
            text.append(f"- {d.get('title')} | {d.get('requester')}")
        await msg.reply_text("\n".join(text))

    @bot.on_message(filters.command("help"))
    async def help_cmd(_, msg: Message):
        await msg.reply_text(
            "/play song name | /skip | /stop | /pause | /resume | /volume 100 | /queue | /history"
        )
