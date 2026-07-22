"""News checker API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, HTTPException, Query

from ..news_checker.analyzer import NewsCheckRequest, news_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news-checker"])


@router.post("/check-credibility")
async def check_credibility(payload: NewsCheckRequest = Body(...)):
    try:
        result = await news_analyzer.analyze(payload)
        return {"success": True, "data": result.model_dump()}
    except Exception as exc:
        # AA4：跟 stock.py/auth.py 一樣先前完全沒有伺服器端記錄，出錯時只能
        # 靠回應內容猜——回應內容維持既有的 str(exc)，不改變既有 API 行為。
        logger.exception("news check-credibility failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/crawled-data")
async def get_crawled_data(
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        items = await news_analyzer.get_crawled_data(source=source, limit=limit)
        return {"success": True, "data": {"items": [item.model_dump() for item in items]}}
    except Exception as exc:
        logger.exception("news crawled-data failed")
        raise HTTPException(status_code=500, detail=str(exc))
