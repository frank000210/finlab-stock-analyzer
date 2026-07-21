"""個股 AI 摘要 API — W2 試點。"""

from fastapi import APIRouter, Depends, HTTPException

from ..analysis.ai_summary import build_ai_summary
from ..data.us_symbols import is_tw_symbol, normalize_symbol
from ..llm import LLMUnavailable, check_llm_rate_limit, is_llm_configured

router = APIRouter(prefix="/api/v1/stocks", tags=["ai-summary"])


@router.get("/{symbol}/ai-summary", dependencies=[Depends(check_llm_rate_limit)])
async def ai_summary(symbol: str):
    """AI 依網站既有數據生成的個股現況摘要。

    延遲 15~40 秒且有 LLM 成本，設計為「使用者主動觸發 + 快取」，前端不可
    放在頁面自動載入路徑上。AI 不可用時回 503，前端降級隱藏此區塊。
    """
    symbol = normalize_symbol(symbol)
    if not is_tw_symbol(symbol):
        raise HTTPException(status_code=404, detail="AI 摘要目前僅支援台股")
    if not is_llm_configured():
        raise HTTPException(status_code=503, detail="AI 服務尚未設定")
    try:
        return {"success": True, "data": await build_ai_summary(symbol)}
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI 摘要產生失敗：{exc}")


@router.get("/ai/status")
async def ai_status():
    """前端用來決定是否顯示 AI 功能入口。"""
    return {"success": True, "data": {"configured": is_llm_configured()}}
