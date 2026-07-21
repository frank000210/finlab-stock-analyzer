"""交易日誌 AI 複盤教練（W6）＋進場理由品質檢查（W7）。

交易日誌全部存在瀏覽器 localStorage，這裡的端點吃前端主動送來的資料，
後端本身沒有交易紀錄的資料庫（跟既有 trade/approval.py 的紙上交易流程
是不同的東西，那個有自己的 Mongo 集合）。
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..analysis.journal_coach import build_ai_coach, check_catalyst_quality
from ..llm import LLMUnavailable, check_llm_rate_limit

router = APIRouter(prefix="/api/v1/journal", tags=["journal-ai"])


class TradeItem(BaseModel):
    """X6：基本合理性檢查——資料來自使用者自己的瀏覽器 localStorage，不是
    外部輸入，不是安全疑慮，但前端若因 bug 送出異常值（例如 NaN 序列化成
    超大數字），沒有防呆的話會被塞進 LLM prompt，讓 AI 複盤根據壞資料生出
    看似合理、實則誤導的分析而使用者不會發現是資料問題。"""

    symbol: str = ""
    side: str = ""
    entry: float | None = None
    exit: float | None = None
    r_multiple: float | None = None
    tag: str = ""
    catalyst: str = ""

    @field_validator("side")
    @classmethod
    def _valid_side(cls, v: str) -> str:
        return v if v in ("long", "short") else ""

    @field_validator("entry", "exit")
    @classmethod
    def _sane_price(cls, v: float | None) -> float | None:
        # 台股沒有股價會到六位數或負數；擋掉明顯壞資料，不做精確業務校驗
        if v is None or not (0 < v < 1_000_000):
            return None
        return v

    @field_validator("r_multiple")
    @classmethod
    def _sane_r(cls, v: float | None) -> float | None:
        if v is None or not (-100 <= v <= 100):
            return None
        return v


class CoachRequest(BaseModel):
    trades: list[TradeItem] = []
    stats: dict = {}


class CatalystRequest(BaseModel):
    symbol: str = ""
    side: str = ""
    catalyst: str


@router.post("/ai-coach", dependencies=[Depends(check_llm_rate_limit)])
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


@router.post("/catalyst-quality", dependencies=[Depends(check_llm_rate_limit)])
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
