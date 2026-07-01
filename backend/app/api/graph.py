"""Watchlist graph APIs: build / snapshot / timeline / alerts."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..analysis.watch_graph import (
    build_watchlist_graph,
    get_watchlist_alerts,
    get_watchlist_snapshot,
    get_watchlist_timeline,
)

router = APIRouter(prefix="/api/v1/graph/watchlist", tags=["watch-graph"])


class BuildGraphRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, description="觀察池股票代碼")
    target_date: date | None = Field(default=None, description="目標日期")
    lookback_days: int = Field(default=60, ge=30, le=365)
    alpha: float = Field(default=0.50, ge=0.0, le=1.0)
    beta: float = Field(default=0.30, ge=0.0, le=1.0)
    gamma: float = Field(default=0.20, ge=0.0, le=1.0)


def _parse_symbols(symbols: str | None) -> list[str]:
    if not symbols:
        return []
    return [segment.strip().upper() for segment in symbols.split(",") if segment.strip()]


@router.post("/build")
async def build_graph(payload: BuildGraphRequest):
    try:
        snapshot = await build_watchlist_graph(
            symbols=payload.symbols,
            target_date=payload.target_date,
            lookback_days=payload.lookback_days,
            force_ingest=True,
            alpha=payload.alpha,
            beta=payload.beta,
            gamma=payload.gamma,
        )
        return {
            "success": True,
            "data": {
                "watchlist_hash": snapshot.get("watchlist_hash"),
                "date": snapshot.get("date"),
                "symbols": snapshot.get("symbols", []),
                "metrics": snapshot.get("metrics", {}),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/snapshot")
async def graph_snapshot(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2317,2454"),
    date_value: date | None = Query(default=None, alias="date", description="目標日期"),
    edge_threshold: float = Query(default=0.35, ge=0.0, le=1.0, description="建邊門檻"),
    lookback_days: int = Query(default=60, ge=30, le=365),
):
    try:
        parsed_symbols = _parse_symbols(symbols)
        snapshot = await get_watchlist_snapshot(
            symbols=parsed_symbols,
            target_date=date_value,
            edge_threshold=edge_threshold,
            lookback_days=lookback_days,
        )
        return {"success": True, "data": snapshot}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/timeline")
async def graph_timeline(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2317,2454"),
    start: date | None = Query(default=None, description="起始日期"),
    end: date | None = Query(default=None, description="結束日期"),
    edge_threshold: float = Query(default=0.35, ge=0.0, le=1.0, description="建邊門檻"),
    lookback_days: int = Query(default=60, ge=30, le=365),
):
    try:
        parsed_symbols = _parse_symbols(symbols)
        end_date = end or date.today()
        start_date = start or (end_date - timedelta(days=30))
        timeline = await get_watchlist_timeline(
            symbols=parsed_symbols,
            start_date=start_date,
            end_date=end_date,
            edge_threshold=edge_threshold,
            lookback_days=lookback_days,
        )
        return {"success": True, "data": timeline}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/alerts")
async def graph_alerts(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2317,2454"),
    edge_threshold: float = Query(default=0.35, ge=0.0, le=1.0, description="建邊門檻"),
):
    try:
        parsed_symbols = _parse_symbols(symbols)
        alerts = await get_watchlist_alerts(parsed_symbols, edge_threshold=edge_threshold)
        return {"success": True, "data": alerts}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

