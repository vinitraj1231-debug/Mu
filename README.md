# Fast Telegram Music Bot

A Telegram music bot optimized for low-latency playback in group voice chats.

## Stack
- Pyrogram for the controller bot and the speaker account
- PyTgCalls for Telegram voice-chat streaming
- Redis for queue/cache/state
- MongoDB for history
- yt-dlp only for resolution, not full downloads

## Why this structure is fast
- The bot resolves a song to a direct media URL once, then caches it in Redis.
- Playback streams the URL directly instead of downloading the whole file.
- Queue operations stay in Redis, so they are fast and lightweight.
- MongoDB stores history and stats without blocking the hot path.

## Install
```bash
pip install -r requirements.txt
cp .env.example .env
```

## Run Redis + MongoDB
```bash
docker compose up -d
```

## Environment
Set:
- API_ID
- API_HASH
- BOT_TOKEN
- SESSION_STRING
- REDIS_URL
- MONGO_URL
- MONGO_DB

## Notes
- The controller is a bot account.
- The audio speaker is a user session because Telegram voice-chat playback is handled through Telegram MTProto voice-call libraries.
- Lavalink is not used in the live Telegram path because it is documented as a Discord voice-server node.
