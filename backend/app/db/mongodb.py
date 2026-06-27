"""MongoDB connection manager using motor (async driver)."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from ..config.settings import get_settings

_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


async def get_mongodb() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance (lazy init)."""
    global _client, _db
    if _db is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        _db = _client[settings.mongodb_db_name]
    return _db


async def close_mongodb():
    """Close MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
