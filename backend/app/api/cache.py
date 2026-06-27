"""Cache management API endpoints."""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])


@router.get("/stats")
async def cache_stats():
    """Get cache statistics."""
    try:
        from ..db.mongodb import get_mongodb
        from ..db.cache import CACHE_TTL
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
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("")
async def clear_cache(
    category: str = Query(default=None, description="清除特定類別快取"),
    symbol: str = Query(default=None, description="清除特定股票快取"),
):
    """Clear cache entries."""
    try:
        from ..db.cache import invalidate_cache
        pattern = f".*{symbol}.*" if symbol else None
        deleted = await invalidate_cache(pattern=pattern, category=category)
        return {"success": True, "data": {"deleted": deleted}}
    except Exception as e:
        return {"success": False, "error": str(e)}
