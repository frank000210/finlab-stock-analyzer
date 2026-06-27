"""News checker API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from ..news_checker.analyzer import NewsCheckRequest, news_analyzer

router = APIRouter(prefix="/api/v1/news", tags=["news-checker"])


@router.post("/check-credibility")
async def check_credibility(payload: NewsCheckRequest = Body(...)):
    try:
        result = await news_analyzer.analyze(payload)
        return {"success": True, "data": result.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/crawled-data")
async def get_crawled_data(
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        items = news_analyzer.get_crawled_data(source=source, limit=limit)
        return {"success": True, "data": {"items": [item.model_dump() for item in items]}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
