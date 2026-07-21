"""交易日誌 AI 複盤教練（W6）＋進場理由品質檢查（W7）。

交易日誌全部存在瀏覽器 localStorage，這裡的端點吃前端主動送來的資料，
後端本身沒有交易紀錄的資料庫（跟既有 trade/approval.py 的紙上交易流程
是不同的東西，那個有自己的 Mongo 集合）。
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ..analysis.journal_coach import build_ai_coach, check_catalyst_quality
from ..llm import LLMUnavailable

router = APIRouter(prefix="/api/v1/journal", tags=["journal-ai"])


class TradeItem(BaseModel):
    symbol: str = ""
    side: str = ""
    entry: float | None = None
    exit: float | None = None
    r_multiple: float | None = None
    tag: str = ""
    catalyst: str = ""


class CoachRequest(BaseModel):
    trades: list[TradeItem] = []
    stats: dict = {}


class CatalystRequest(BaseModel):
    symbol: str = ""
    side: str = ""
    catalyst: str


@router.post("/ai-coach")
async def ai_coach(payload: CoachRequest = Body(...)):
    """W6：LLM 分析一批已平倉交易，找規則式教練沒設計到的細緻行為模式。"""
    if not payload.trades:
        raise HTTPException(status_code=400, detail="沒有可分析的交易紀錄")
    if len(payload.trades) < 10:
        raise HTTPException(status_code=400, detail="已平倉交易少於 10 筆，樣本太少不適合 AI 分析")
    try:
        trades = [t.model_dump() for t in payload.trades][-60:]  # 上限避免 prompt 過大
        return {"success": True, "data": await build_ai_coach(trades, payload.stats)}
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 複盤失敗：{exc}")


@router.post("/catalyst-quality")
async def catalyst_quality(payload: CatalystRequest = Body(...)):
    """W7：檢查單一進場理由是否具體可驗證，而非空泛主觀。"""
    text = payload.catalyst.strip()
    if not text:
        raise HTTPException(status_code=400, detail="請先填寫進場理由")
    if len(text) > 300:
        text = text[:300]
    try:
        return {"success": True, "data": await check_catalyst_quality(payload.symbol, payload.side, text)}
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"理由品質檢查失敗：{exc}")
