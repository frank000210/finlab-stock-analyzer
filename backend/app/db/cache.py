"""Cache layer using MongoDB with TTL support.

Collections:
- cache: General API response cache (auto-expires via TTL index)
- settings: User settings and preferences
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from .mongodb import get_mongodb


# Default TTL for different data types (in minutes)
CACHE_TTL = {
    "stock_price": 30,        # 股價 30 分鐘
    "analysis": 60,           # 分析結果 1 小時
    "seasonal": 1440,         # 季節性分析 1 天
    "lead_lag": 720,          # 領先落後 12 小時
    "major_players": 60,      # 主力動向 1 小時
    "social_buzz": 30,        # 社群熱度 30 分鐘
    "public_data": 360,       # 公開資料 6 小時
    "financial": 1440,        # 財報 1 天
    "backtest": 1440,         # 回測 1 天
}


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
    """Create TTL index on cache collection (call once at startup)."""
    db = await get_mongodb()
    await db.cache.create_index("expires_at", expireAfterSeconds=0)
    await db.cache.create_index([("key", 1)], unique=True)
    await db.settings.create_index([("key", 1)], unique=True)


async def get_cache(key: str) -> Optional[Any]:
    """Get cached data by key. Returns None if not found or expired."""
    db = await get_mongodb()
    doc = await db.cache.find_one({"key": key, "expires_at": {"$gt": datetime.utcnow()}})
    if doc:
        raw = doc.get("data")
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    return None


async def set_cache(key: str, data: Any, category: str = "analysis") -> None:
    """Set cache with TTL based on category."""
    db = await get_mongodb()
    ttl_minutes = CACHE_TTL.get(category, 60)
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

    serialized = _serialize(data)

    await db.cache.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "data": serialized,
            "category": category,
            "expires_at": expires_at,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )


async def invalidate_cache(pattern: str = None, category: str = None) -> int:
    """Invalidate cache entries. Use pattern for key prefix, or category."""
    db = await get_mongodb()
    query = {}
    if pattern:
        query["key"] = {"$regex": f"^{pattern}"}
    if category:
        query["category"] = category
    result = await db.cache.delete_many(query)
    return result.deleted_count


# --- Settings ---

async def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value."""
    db = await get_mongodb()
    doc = await db.settings.find_one({"key": key})
    if doc:
        return doc.get("value", default)
    return default


async def set_setting(key: str, value: Any) -> None:
    """Set a setting value."""
    db = await get_mongodb()
    await db.settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "updated_at": datetime.utcnow()}},
        upsert=True,
    )


async def get_all_settings() -> dict:
    """Get all settings as a dictionary."""
    db = await get_mongodb()
    cursor = db.settings.find({})
    settings = {}
    async for doc in cursor:
        settings[doc["key"]] = doc.get("value")
    return settings
