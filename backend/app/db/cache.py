"""Cache layer using MongoDB with TTL support.

Collections:
- cache: General API response cache (auto-expires via TTL index)
- settings: User settings and preferences
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

try:
    from .mongodb import get_mongodb
except Exception:
    get_mongodb = None


# Default TTL for different data types (in minutes)
CACHE_TTL = {
    "stock_price": 30,
    "analysis": 60,
    "seasonal": 1440,
    "lead_lag": 720,
    "major_players": 60,
    "chip": 60,
    "social_buzz": 30,
    "public_data": 360,
    "financial": 1440,
    "backtest": 1440,
    # U1 同業比較：PE 等估值日頻更新、營收月頻、財報季頻，比較表整包快取
    # 6 小時已足夠新鮮；全市場日行情一天只需要抓一次。
    "peer": 360,
    "market_quotes": 720,
    # V1 大盤多空儀表板：期貨部位/融資餘額皆為日頻盤後資料，60 分鐘足夠
    "market_lights": 60,
}


async def _get_db():
    if get_mongodb is None:
        raise RuntimeError("MongoDB is unavailable.")
    return await get_mongodb()


def _serialize(data: Any) -> str:
    """Serialize data to JSON string, handling numpy/pandas types."""
    import numpy as np

    def default_handler(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)

    return json.dumps(data, default=default_handler, ensure_ascii=False)


async def ensure_indexes():
    """Create indexes for cache and settings collections."""
    db = await _get_db()
    await db.cache.create_index("expires_at", expireAfterSeconds=0)
    await db.cache.create_index([("key", 1)], unique=True)
    await db.settings.create_index([("key", 1)], unique=True)


async def get_cache(key: str) -> Optional[Any]:
    """Get cached data by key. Returns None if not found or expired."""
    db = await _get_db()
    doc = await db.cache.find_one({"key": key, "expires_at": {"$gt": datetime.utcnow()}})
    if doc:
        raw = doc.get("data")
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    return None


async def set_cache(key: str, data: Any, category: str = "analysis") -> None:
    """Set cache with TTL based on category."""
    db = await _get_db()
    ttl_minutes = CACHE_TTL.get(category, 60)
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    serialized = _serialize(data)
    await db.cache.update_one(
        {"key": key},
        {
            "$set": {
                "key": key,
                "data": serialized,
                "category": category,
                "expires_at": expires_at,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )


async def invalidate_cache(pattern: str = None, category: str = None) -> int:
    """Invalidate cache entries. Use pattern for key prefix, or category."""
    db = await _get_db()
    query = {}
    if pattern:
        query["key"] = {"$regex": f"^{pattern}"}
    if category:
        query["category"] = category
    result = await db.cache.delete_many(query)
    return result.deleted_count


async def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value."""
    db = await _get_db()
    doc = await db.settings.find_one({"key": key})
    if doc:
        return doc.get("value", default)
    return default


async def set_setting(key: str, value: Any) -> None:
    """Set a setting value."""
    db = await _get_db()
    await db.settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "updated_at": datetime.utcnow()}},
        upsert=True,
    )


async def get_all_settings() -> dict:
    """Get all settings as a dictionary."""
    db = await _get_db()
    cursor = db.settings.find({})
    settings = {}
    async for doc in cursor:
        settings[doc["key"]] = doc.get("value")
    return settings
