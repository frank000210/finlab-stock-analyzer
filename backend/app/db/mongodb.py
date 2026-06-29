"""MongoDB connection manager using motor (async driver)."""

from typing import Any

from ..config.settings import get_settings

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
except Exception:
    AsyncIOMotorClient = None
    AsyncIOMotorDatabase = Any

_client = None
_db = None


async def get_mongodb():
    """Get MongoDB database instance (lazy init)."""
    global _client, _db
    if AsyncIOMotorClient is None:
        raise RuntimeError("motor is not available. MongoDB features are disabled.")
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
