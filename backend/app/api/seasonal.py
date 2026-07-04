"""Seasonal analysis API endpoint."""

from fastapi import APIRouter, Query, HTTPException

from ..analysis.seasonal import analyze_seasonal_patterns

router = APIRouter(prefix="/api/v1/stocks", tags=["seasonal"])


@router.get("/{symbol}/seasonal")
async def get_seasonal_analysis(
    symbol: str,
    years: int = Query(default=5, ge=2, le=10, description="分析年數"),
):
    """Get seasonal pattern analysis for a stock."""
    try:
        # Check cache
        cache_key = f"seasonal:v1:{symbol}:{years}"
        try:
            from ..db.cache import get_cache, set_cache
            cached = await get_cache(cache_key)
            if cached:
                return {"success": True, "data": cached}
        except Exception:
            pass

        result = await analyze_seasonal_patterns(symbol, years)
        if "error" in result:
            return {"success": False, "error": result["error"], "data": None}

        # Store in cache
        try:
            await set_cache(cache_key, result, "seasonal")
        except Exception:
            pass

        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
