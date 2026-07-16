"""Social Buzz (社群熱度) API endpoint."""

import logging

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/stocks", tags=["social-buzz"])
logger = logging.getLogger(__name__)


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
        # R2：完整 traceback 只記到伺服器端日誌，不回傳給呼叫端——之前直接把
        # traceback.format_exc() 塞進 API 回應，等於把內部檔案路徑、套件版本
        # 洩漏給任何匿名呼叫者（跟 H1 修過的 FinMind token 洩漏是同類問題）。
        logger.exception("social-buzz analysis failed for %s", symbol)
        return {"success": False, "error": f"社群熱度分析失敗：{e}"}
