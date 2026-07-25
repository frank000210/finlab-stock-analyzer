"""大盤多空儀表板 API — V1."""

import logging

from fastapi import APIRouter, HTTPException

from ..analysis.market_lights import build_market_lights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/lights")
async def market_lights():
    """三燈大盤多空儀表板：趨勢（A 級）＋外資期貨（B 級）＋融資（B 級），
    輸出「體制（多方/空方/僵持）× 信心度」。"""
    try:
        return {"success": True, "data": await build_market_lights()}
    except Exception as exc:
        logger.exception("market_lights failed")
        raise HTTPException(status_code=502, detail=f"大盤多空儀表板查詢失敗：{exc}")
