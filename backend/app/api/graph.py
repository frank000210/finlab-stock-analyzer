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
from ..db.memcache import mem_clear, mem_get, mem_set

router = APIRouter(prefix="/api/v1/graph/watchlist", tags=["watch-graph"])


class BuildGraphRequest(BaseModel):
    # AA2：ingest_watchlist_raw() 對每個代碼都是逐一循序打外部 API + 逐筆
    # 寫入 Mongo，沒有上限的話一個異常大的 symbols 陣列會讓單一請求跑非常
    # 久。100 檔已遠超過正常觀察清單規模，純粹是防呆上限，不影響一般使用。
    symbols: list[str] = Field(default_factory=list, max_length=100, description="觀察池股票代碼")
    target_date: date | None = Field(default=None, description="目標日期")
    lookback_days: int = Field(default=60, ge=30, le=365)
    alpha: float = Field(default=0.50, ge=0.0, le=1.0)
    beta: float = Field(default=0.30, ge=0.0, le=1.0)
    gamma: float = Field(default=0.20, ge=0.0, le=1.0)


def _parse_symbols(symbols: str | None) -> list[str]:
    if not symbols:
        return []
    return [segment.strip().upper() for segment in symbols.split(",") if segment.strip()]


def _raise_graph_error(exc: Exception) -> None:
    message = str(exc or "")
    lower = message.lower()
    if "payment required" in lower or "token=" in lower or "finmind" in lower:
        raise HTTPException(status_code=502, detail="Graph 資料源授權失敗，請檢查 FinMind 權限或稍後再試。")
    raise HTTPException(status_code=500, detail="Graph 計算失敗，請稍後重試。")


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
        mem_clear("graph:")  # 重建後舊的節點/邊快取全部失效
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
        _raise_graph_error(exc)


@router.get("/snapshot")
async def graph_snapshot(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2317,2454"),
    date_value: date | None = Query(default=None, alias="date", description="目標日期"),
    edge_threshold: float = Query(default=0.12, ge=0.0, le=1.0, description="建邊門檻"),
    lookback_days: int = Query(default=60, ge=30, le=365),
):
    try:
        parsed_symbols = _parse_symbols(symbols)
        cache_key = f"graph:snapshot:{','.join(parsed_symbols)}:{date_value}:{edge_threshold}:{lookback_days}"
        cached = mem_get(cache_key)
        if cached is not None:
            return {"success": True, "data": cached}
        snapshot = await get_watchlist_snapshot(
            symbols=parsed_symbols,
            target_date=date_value,
            edge_threshold=edge_threshold,
            lookback_days=lookback_days,
        )
        mem_set(cache_key, snapshot)
        return {"success": True, "data": snapshot}
    except Exception as exc:
        _raise_graph_error(exc)


@router.get("/timeline")
async def graph_timeline(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2317,2454"),
    start: date | None = Query(default=None, description="起始日期"),
    end: date | None = Query(default=None, description="結束日期"),
    edge_threshold: float = Query(default=0.12, ge=0.0, le=1.0, description="建邊門檻"),
    lookback_days: int = Query(default=60, ge=30, le=365),
):
    try:
        parsed_symbols = _parse_symbols(symbols)
        end_date = end or date.today()
        start_date = start or (end_date - timedelta(days=30))
        cache_key = f"graph:timeline:{','.join(parsed_symbols)}:{start_date}:{end_date}:{edge_threshold}:{lookback_days}"
        cached = mem_get(cache_key)
        if cached is not None:
            return {"success": True, "data": cached}
        timeline = await get_watchlist_timeline(
            symbols=parsed_symbols,
            start_date=start_date,
            end_date=end_date,
            edge_threshold=edge_threshold,
            lookback_days=lookback_days,
        )
        mem_set(cache_key, timeline)
        return {"success": True, "data": timeline}
    except Exception as exc:
        _raise_graph_error(exc)


@router.get("/alerts")
async def graph_alerts(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2317,2454"),
    edge_threshold: float = Query(default=0.12, ge=0.0, le=1.0, description="建邊門檻"),
):
    try:
        parsed_symbols = _parse_symbols(symbols)
        cache_key = f"graph:alerts:{','.join(parsed_symbols)}:{edge_threshold}"
        cached = mem_get(cache_key)
        if cached is not None:
            return {"success": True, "data": cached}
        alerts = await get_watchlist_alerts(parsed_symbols, edge_threshold=edge_threshold)
        mem_set(cache_key, alerts)
        return {"success": True, "data": alerts}
    except Exception as exc:
        _raise_graph_error(exc)
