"""Social Buzz (社群熱度) API endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..llm import check_llm_rate_limit

router = APIRouter(prefix="/api/v1/stocks", tags=["social-buzz"])
logger = logging.getLogger(__name__)

# JJ5：get_social_buzz 每次未命中快取都會即時打 PTT/Google News/財經媒體/
# 事實查核共 4-6 次外部 HTTP 抓取，先前完全沒有頻率限制——攻擊者只要在
# 路徑帶入不同的無效代號（快取鍵是原始 symbol 字串）就能每次都繞過 30
# 分鐘快取，逼後端無限次重抓，除了拖垮自身資源，也有把共用對外 IP 弄到
# 被 PTT/Google/TFC 封鎖、連累所有正常使用者的風險。門檻比 LLM 節流寬鬆
# （這裡沒有 LLM 成本），但比 analytics.py 的單純寫日誌嚴格（這裡每次都是
# 真的對外爬蟲）。
_BUZZ_WINDOW_MINUTES = 10
# OverviewView.vue 每次載入都會打這支（見 OverviewView.vue 的
# socialBuzz fetch），加上直接造訪本頁與 AI 摘要頁的次數，正常瀏覽在
# 10 分鐘內輕鬆兩位數——門檻抓寬鬆一點，只擋真正異常的洗量。
_BUZZ_MAX_CALLS = 60


async def _check_buzz_rate_limit(request: Request) -> None:
    from ..api.analytics import _get_client_ip
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    if not ip or ip == "unknown":
        return
    try:
        count = await increment_rate_limit(f"social_buzz_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _BUZZ_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"查詢過於頻繁，請 {_BUZZ_WINDOW_MINUTES} 分鐘後再試。",
        )


@router.get("/{symbol}/social-buzz/history")
async def get_social_buzz_history(symbol: str, days: int = Query(default=30, ge=1, le=365)):
    """近 N 天的每日熱度快照，供前端畫趨勢走勢用。"""
    try:
        from ..analysis.social_buzz import get_buzz_history
        history = await get_buzz_history(symbol, days)
        return {"success": True, "data": history}
    except Exception as e:
        logger.exception("social-buzz history failed for %s", symbol)
        return {"success": False, "error": str(e)}


@router.get("/{symbol}/social-buzz/ai-summary", dependencies=[Depends(check_llm_rate_limit)])
async def get_news_ai_summary(symbol: str):
    """W4：LLM 把已抓到的 PTT/新聞/財經媒體標題摘成白話輿情判讀。

    只總結已抓到的標題清單，不杜撰內容；使用者主動觸發、快取 6 小時，
    跟 W2 個股 AI 摘要同樣的節奏。
    """
    from ..llm import LLMUnavailable, is_llm_configured

    if not is_llm_configured():
        return {"success": False, "error": "AI 服務尚未設定"}
    try:
        from ..analysis.news_summary import build_news_ai_summary
        from ..analysis.social_buzz import analyze_social_buzz
        from ..ai_agent.signal_generator import STOCK_NAMES

        stock_name = STOCK_NAMES.get(symbol, "")
        buzz = await analyze_social_buzz(symbol, stock_name)
        result = await build_news_ai_summary(symbol, buzz)
        return {"success": True, "data": result}
    except LLMUnavailable as exc:
        return {"success": False, "error": str(exc)}
    except Exception as e:
        logger.exception("news AI summary failed for %s", symbol)
        return {"success": False, "error": f"新聞摘要產生失敗：{e}"}


@router.get("/{symbol}/social-buzz", dependencies=[Depends(_check_buzz_rate_limit)])
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
