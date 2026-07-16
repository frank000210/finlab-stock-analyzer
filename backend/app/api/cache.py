"""Cache management API endpoints."""

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from .admin import require_admin

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])

# R1：/reingest 觸發的是排程本來就會跑的重量級工作（類股輪動+關聯圖重抓），
# 是一般使用者在設定頁就能點的正常功能（非管理員限定），所以不能像
# /stats、DELETE 一樣直接掛 admin 驗證——那樣會擋掉現有正常用法。改成簡單
# 的行程內冷卻時間，擋掉短時間內重複觸發造成的濫用/成本放大，不影響偶爾
# 手動更新一次的正常使用情境。
_REINGEST_COOLDOWN_SEC = 300
_last_reingest_at: float = 0.0


@router.get("/stats")
async def cache_stats(_admin: dict = Depends(require_admin)):
    """Get cache statistics."""
    try:
        from ..db.mongodb import get_mongodb
        from ..db.cache import CACHE_TTL
        from ..db.memory_cache import sizes as memory_cache_sizes
        from datetime import datetime

        db = await get_mongodb()
        total = await db.cache.count_documents({})
        active = await db.cache.count_documents({"expires_at": {"$gt": datetime.utcnow()}})

        pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]
        categories = {}
        async for doc in db.cache.aggregate(pipeline):
            categories[doc["_id"] or "unknown"] = doc["count"]

        return {
            "success": True,
            "data": {
                "total_entries": total,
                "active_entries": active,
                "expired_entries": total - active,
                "categories": categories,
                "ttl_config": CACHE_TTL,
                "memory_caches": memory_cache_sizes(),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("")
async def clear_cache(
    category: str = Query(default=None, description="清除特定類別快取"),
    symbol: str = Query(default=None, description="清除特定股票快取"),
    _admin: dict = Depends(require_admin),
):
    """Clear cache entries."""
    try:
        from ..db.cache import invalidate_cache
        from ..db.memory_cache import clear as clear_memory_cache

        pattern = f".*{symbol}.*" if symbol else None
        deleted = await invalidate_cache(pattern=pattern, category=category)
        # in-memory 快取一併清除:有指定 category 時只清同名者,否則全清
        memory_cleared = clear_memory_cache(category)
        return {"success": True, "data": {"deleted": deleted, "memory_cleared": memory_cleared}}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/reingest")
async def reingest_now():
    """手動立即執行一次「每日排程」的 re-ingest（類股輪動指數＋關聯圖觀察池），
    並清掉圖/輪動記憶體快取。跟每日排程做的事完全一樣，供需要時手動觸發。"""
    global _last_reingest_at
    now = time.monotonic()
    remaining = _REINGEST_COOLDOWN_SEC - (now - _last_reingest_at)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail=f"更新太頻繁，請 {int(remaining)} 秒後再試（避免重複觸發昂貴的重抓作業）。",
        )
    try:
        from ..scheduler import _run_once

        await _run_once()
        _last_reingest_at = now
        return {"success": True, "data": {"status": "reingested"}}
    except Exception as e:
        return {"success": False, "error": str(e)}
