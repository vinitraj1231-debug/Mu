from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient


class MongoStore:
    def __init__(self, url: str, db_name: str) -> None:
        self.client = AsyncIOMotorClient(url)
        self.db = self.client[db_name]
        self.history = self.db["history"]
        self.stats = self.db["stats"]

    async def add_history(self, document: dict) -> None:
        await self.history.insert_one(document)

    async def increment_stat(self, key: str, value: int = 1) -> None:
        await self.stats.update_one({"_id": key}, {"$inc": {"count": value}}, upsert=True)

    async def get_top_queries(self, limit: int = 10) -> list[dict]:
        cursor = self.history.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
