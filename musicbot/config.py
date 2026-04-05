from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    session_string: str
    redis_url: str
    mongo_url: str
    mongo_db: str
    default_volume: int
    bot_username: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            api_id=int(_env("API_ID", required=True)),
            api_hash=_env("API_HASH", required=True),
            bot_token=_env("BOT_TOKEN", required=True),
            session_string=_env("SESSION_STRING", required=True),
            redis_url=_env("REDIS_URL", "redis://localhost:6379/0"),
            mongo_url=_env("MONGO_URL", "mongodb://localhost:27017"),
            mongo_db=_env("MONGO_DB", "telegram_music_bot"),
            default_volume=int(_env("DEFAULT_VOLUME", "100")),
            bot_username=_env("BOT_USERNAME", ""),
        )


settings = Settings.load()
