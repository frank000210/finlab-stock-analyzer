"""Cache layer using MongoDB with TTL support.

Collections:
- cache: General API response cache (auto-expires via TTL index)
- settings: User settings and preferences
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from pymongo import ReturnDocument

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
    # W2 AI 摘要：來源多為日頻資料，且每次呼叫都有 LLM 成本與 15~40 秒延遲，
    # 快取拉長到 6 小時（cache key 另含日期，跨日自然失效）
    "ai_summary": 360,
    # X1：LLM 端點 per-IP 節流窗口，10 分鐘
    "rate_limit": 10,
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


async def push_to_setting_array(key: str, item: Any) -> None:
    """Atomically append an item to a list-valued setting via Mongo $push.

    JJ4：risk.py 的 create_alert/delete_alert 先前是「get_setting() 讀出
    整個 list、在 Python 端修改、set_setting() 整份寫回」，兩個並行請求
    （雙擊、兩個分頁）可能各自讀到同一份舊 list，其中一個的寫入會被另一
    個覆蓋掉——不是「同時新增兩筆各自成功」，而是其中一筆平白消失。改用
    $push 讓新增本身是原子操作，不管多少個並行請求同時打進來都不會互相
    覆蓋。
    """
    db = await _get_db()
    await db.settings.find_one_and_update(
        {"key": key},
        {
            "$push": {"value": item},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {"key": key},
        },
        upsert=True,
    )


async def pull_from_setting_array(key: str, match_field: str, match_value: Any) -> bool:
    """Atomically remove the array element(s) where item[match_field] ==
    match_value from a list-valued setting via Mongo $pull.

    Returns True if a matching element existed immediately before the pull
    (and was therefore removed), False otherwise — lets the caller
    distinguish "deleted" from "already gone" (e.g. for a 404) without a
    separate, non-atomic read.
    """
    db = await _get_db()
    before = await db.settings.find_one_and_update(
        {"key": key},
        {"$pull": {"value": {match_field: match_value}}, "$set": {"updated_at": datetime.utcnow()}},
    )
    if not before:
        return False
    return any(
        isinstance(item, dict) and item.get(match_field) == match_value
        for item in before.get("value", [])
    )


async def increment_setting(key: str, amount: int = 1) -> int:
    """Atomically increment a numeric setting and return the new (post-increment) value.

    HH6：llm/client.py 原本是 get_setting() 讀值、比對門檻、再 set_setting()
    寫回——三個步驟不是原子的，不同來源的並行請求可能同時讀到同一個舊值，
    全域每日額度就可能被超額打穿。改用 Mongo 的 $inc 讓遞增本身是原子操作，
    不管多少個並行請求同時打進來，每個請求拿到的都是彼此不同、嚴格遞增的
    回傳值，天然避免 race。
    """
    db = await _get_db()
    doc = await db.settings.find_one_and_update(
        {"key": key},
        {"$inc": {"value": amount}, "$set": {"updated_at": datetime.utcnow()}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc.get("value", 0))


async def increment_rate_limit(key: str, category: str = "rate_limit") -> int:
    """Atomically increment a sliding-window rate-limit counter and refresh
    its TTL, returning the new (post-increment) count.

    II4：llm/rate_limit.py 原本是 get_cache() 讀值、比對門檻、再 set_cache()
    寫回，跟 HH6 修過的全域額度是同一種 race——並行請求可能同時讀到同一個
    舊值，單一 IP 就能繞過限流打穿全站共用的每日額度。不能直接沿用
    increment_setting()：那是寫進不會過期的 settings collection，如果拿來
    存「每個 IP 各一筆」的計數器，會變成另一種無上限成長（每個出現過的 IP
    留一筆設定，永遠不刪）。這裡改在本來就有 TTL 索引的 cache collection
    上做原子 $inc，且每次呼叫都順便刷新 expires_at，維持原本「滑動視窗」
    的語意。
    """
    db = await _get_db()
    ttl_minutes = CACHE_TTL.get(category, 60)
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    doc = await db.cache.find_one_and_update(
        {"key": key},
        {
            "$inc": {"count": 1},
            "$set": {"category": category, "expires_at": expires_at, "updated_at": datetime.utcnow()},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc.get("count", 0))


async def get_all_settings() -> dict:
    """Get all settings as a dictionary."""
    db = await _get_db()
    cursor = db.settings.find({})
    settings = {}
    async for doc in cursor:
        settings[doc["key"]] = doc.get("value")
    return settings


async def add_to_setting_list(key: str, item: Any) -> list:
    """RR6: 原子地將 item 加入清單型設定（MongoDB $addToSet）。

    讀改寫三步驟在並行請求下可能互相覆蓋——例如兩個請求同時新增不同 email，
    後寫的一方覆蓋先寫的，導致先寫的 email 消失。$addToSet 讓整個操作原子化，
    不管多少並行請求都不會互相覆蓋，也自動去重。
    回傳操作後的最新清單。
    """
    db = await _get_db()
    doc = await db.settings.find_one_and_update(
        {"key": key},
        {
            "$addToSet": {"value": item},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {"key": key},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return list(doc.get("value") or [])


async def remove_from_setting_list(key: str, item: Any) -> list:
    """RR6: 原子地從清單型設定中移除 item（MongoDB $pull）。

    回傳操作後的最新清單。
    """
    db = await _get_db()
    doc = await db.settings.find_one_and_update(
        {"key": key},
        {
            "$pull": {"value": item},
            "$set": {"updated_at": datetime.utcnow()},
        },
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        return []
    return list(doc.get("value") or [])
