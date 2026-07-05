"""Sector rotation APIs: build / snapshot / timeline / ranking."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..analysis.sector_rotation import (
    get_daily_heatmap,
    get_rotation_snapshot,
    get_rotation_timeline,
    ingest_sector_index,
)
from ..analysis.watch_graph import ingest_watchlist_raw
from ..db.memcache import mem_clear, mem_get, mem_set

router = APIRouter(prefix="/api/v1/rotation", tags=["sector-rotation"])


class BuildRotationRequest(BaseModel):
    universe: str = Field(default="twse", pattern="^(twse|watchlist)$")
    symbols: list[str] = Field(default_factory=list, description="watchlist universe 專用")
    end: date | None = Field(default=None)
    lookback_days: int = Field(default=400, ge=60, le=1100)


def _parse_symbols(symbols: str | None) -> list[str]:
    if not symbols:
        return []
    return [segment.strip().upper() for segment in symbols.split(",") if segment.strip()]


def _raise_rotation_error(exc: Exception) -> None:
    message = str(exc or "").lower()
    if "payment required" in message or "token=" in message or "finmind" in message:
        raise HTTPException(status_code=502, detail="輪動資料源授權失敗，請稍後再試。")
    raise HTTPException(status_code=500, detail="類股輪動計算失敗，請稍後重試。")


@router.post("/build")
async def build_rotation(payload: BuildRotationRequest):
    try:
        end = payload.end or date.today()
        start = end - timedelta(days=payload.lookback_days)
        if payload.universe == "watchlist":
            result = await ingest_watchlist_raw(payload.symbols, start, end)
        else:
            result = await ingest_sector_index(start, end)
        mem_clear("rotation:")  # 原始資料重抓後，記憶體裡的輪動計算結果全部失效
        return {"success": True, "data": {"universe": payload.universe, **result}}
    except HTTPException:
        raise
    except Exception as exc:
        _raise_rotation_error(exc)


@router.get("/snapshot")
async def rotation_snapshot(
    universe: str = Query(default="twse", pattern="^(twse|watchlist)$"),
    freq: str = Query(default="daily", pattern="^(daily|weekly)$"),
    date_value: date | None = Query(default=None, alias="date"),
    symbols: str | None = Query(default=None, description="watchlist universe 逗號分隔代碼"),
    lookback_days: int = Query(default=400, ge=60, le=1100),
    trail_length: int = Query(default=10, ge=2, le=24),
    edge_threshold: float = Query(default=0.25, ge=0.0, le=1.0),
):
    try:
        parsed = _parse_symbols(symbols)
        cache_key = f"rotation:snapshot:{universe}:{freq}:{date_value}:{','.join(parsed)}:{lookback_days}:{trail_length}:{edge_threshold}"
        cached = mem_get(cache_key)
        if cached is not None:
            return {"success": True, "data": cached}
        snapshot = await get_rotation_snapshot(
            universe=universe,
            freq=freq,
            target_date=date_value,
            symbols=parsed,
            lookback_days=lookback_days,
            trail_length=trail_length,
            edge_threshold=edge_threshold,
        )
        mem_set(cache_key, snapshot)
        return {"success": True, "data": snapshot}
    except Exception as exc:
        _raise_rotation_error(exc)


@router.get("/timeline")
async def rotation_timeline(
    universe: str = Query(default="twse", pattern="^(twse|watchlist)$"),
    freq: str = Query(default="daily", pattern="^(daily|weekly)$"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    symbols: str | None = Query(default=None),
    lookback_days: int = Query(default=400, ge=60, le=1100),
):
    try:
        end_date = end or date.today()
        start_date = start or (end_date - timedelta(days=60))
        parsed = _parse_symbols(symbols)
        cache_key = f"rotation:timeline:{universe}:{freq}:{start_date}:{end_date}:{','.join(parsed)}:{lookback_days}"
        cached = mem_get(cache_key)
        if cached is not None:
            return {"success": True, "data": cached}
        timeline = await get_rotation_timeline(
            universe=universe,
            freq=freq,
            start_date=start_date,
            end_date=end_date,
            symbols=parsed,
            lookback_days=lookback_days,
        )
        mem_set(cache_key, timeline)
        return {"success": True, "data": timeline}
    except Exception as exc:
        _raise_rotation_error(exc)


@router.get("/heatmap")
async def rotation_heatmap(
    universe: str = Query(default="twse", pattern="^(twse|watchlist)$"),
    date_value: date | None = Query(default=None, alias="date"),
    symbols: str | None = Query(default=None, description="watchlist universe 逗號分隔代碼"),
    lookback_days: int = Query(default=10, ge=2, le=60),
):
    """每日漲跌熱力圖（Treemap）：類股/觀察池今天對昨天的漲跌幅快照。"""
    try:
        parsed = _parse_symbols(symbols)
        cache_key = f"rotation:heatmap:{universe}:{date_value}:{','.join(parsed)}:{lookback_days}"
        cached = mem_get(cache_key)
        if cached is not None:
            return {"success": True, "data": cached}
        data = await get_daily_heatmap(
            universe=universe,
            target_date=date_value,
            symbols=parsed,
            lookback_days=lookback_days,
        )
        mem_set(cache_key, data)
        return {"success": True, "data": data}
    except Exception as exc:
        _raise_rotation_error(exc)


@router.get("/ranking")
async def rotation_ranking(
    universe: str = Query(default="twse", pattern="^(twse|watchlist)$"),
    freq: str = Query(default="daily", pattern="^(daily|weekly)$"),
    date_value: date | None = Query(default=None, alias="date"),
    symbols: str | None = Query(default=None),
    lookback_days: int = Query(default=400, ge=60, le=1100),
):
    try:
        parsed = _parse_symbols(symbols)
        cache_key = f"rotation:ranking:{universe}:{freq}:{date_value}:{','.join(parsed)}:{lookback_days}"
        cached = mem_get(cache_key)
        if cached is None:
            cached = await get_rotation_snapshot(
                universe=universe,
                freq=freq,
                target_date=date_value,
                symbols=parsed,
                lookback_days=lookback_days,
            )
            mem_set(cache_key, cached)
        snapshot = cached
        return {
            "success": True,
            "data": {
                "date": snapshot.get("date"),
                "freq": freq,
                "universe": universe,
                "items": snapshot.get("ranking", []),
            },
        }
    except Exception as exc:
        _raise_rotation_error(exc)
