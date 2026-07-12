"""Social Buzz (社群熱度) API endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/stocks", tags=["social-buzz"])


@router.get("/{symbol}/social-buzz/history")
async def get_social_buzz_history(symbol: str, days: int = 30):
    """近 N 天的每日熱度快照，供前端畫趨勢走勢用。"""
    try:
        from ..analysis.social_buzz import get_buzz_history
        history = await get_buzz_history(symbol, days)
        return {"success": True, "data": history}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/{symbol}/social-buzz")
async def get_social_buzz(symbol: str):
    """Analyze social media and news buzz for a stock."""
    try:
        cache_key = f"social_buzz:v1:{symbol}"
        try:
            from ..db.cache import get_cache, set_cache
            cached = await get_cache(cache_key)
            if cached:
                return {"success": True, "data": cached}
        except Exception:
            pass

        from ..analysis.social_buzz import analyze_social_buzz
        from ..ai_agent.signal_generator import STOCK_NAMES

        stock_name = STOCK_NAMES.get(symbol, "")
        result = await analyze_social_buzz(symbol, stock_name)

        try:
            await set_cache(cache_key, result, "social_buzz")
        except Exception:
            pass

        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "detail": traceback.format_exc()[-800:]}
