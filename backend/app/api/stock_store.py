"""每日資料庫 API：白名單、手動觸發、狀態、讀取已存資料。

- 白名單／觸發／狀態都要管理員 token（跟價格警報一樣）。
- 讀已存資料是唯讀、不打 FinMind，不需要登入。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ..data import stock_store as store
from .admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/store", tags=["stock-store"])

_bg: set[asyncio.Task] = set()


class WhitelistReq(BaseModel):
    symbols: list[str] = []


class RunReq(BaseModel):
    symbols: Optional[list[str]] = None  # 不給就用白名單
    datasets: Optional[list[str]] = None


def _ok(data):
    return {"success": True, "data": jsonable_encoder(data)}


@router.get("/whitelist", dependencies=[Depends(require_admin)])
async def get_whitelist():
    return _ok({**(await store.get_whitelist()), "max_symbols": store.MAX_SYMBOLS})


@router.put("/whitelist", dependencies=[Depends(require_admin)])
async def put_whitelist(req: WhitelistReq):
    try:
        symbols = await store.set_whitelist(req.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _ok({"symbols": symbols, "source": "db"})


@router.get("/status", dependencies=[Depends(require_admin)])
async def status():
    return _ok(await store.get_status())


@router.post("/run", dependencies=[Depends(require_admin)])
async def run(req: RunReq):
    """背景跑一輪增量同步，立刻回應；進度看 /status。"""
    if store.is_running():
        return _ok({"started": False, "reason": "already_running"})
    if req.datasets is not None:
        bad = [d for d in req.datasets if d not in store.DATASETS]
        if bad:
            raise HTTPException(status_code=400, detail=f"未知的資料集：{','.join(bad)}")
    try:
        symbols = store.normalize_symbols(req.symbols) if req.symbols is not None else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    task = asyncio.create_task(store.run_sync(symbols=symbols, datasets=req.datasets, trigger="manual"))
    _bg.add(task)
    task.add_done_callback(_bg.discard)
    return _ok({"started": True})


@router.get("/data/{dataset}/{symbol}")
async def read_data(
    dataset: str,
    symbol: str,
    start: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=500, ge=1, le=2000),
):
    if dataset not in store.DATASETS:
        raise HTTPException(status_code=400, detail=f"未知的資料集：{dataset}")
    try:
        sym = store.normalize_symbols([symbol])[0]
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="代號格式不正確") from None
    db = await store._db()
    q: dict = {"symbol": sym}
    if start or end:
        q["date"] = {**({"$gte": start} if start else {}), **({"$lte": end} if end else {})}
    rows = await db[store.DATASETS[dataset]["coll"]].find(q, {"_id": 0}).sort("date", -1).limit(limit).to_list(length=limit)
    rows.reverse()  # 由舊到新
    return _ok({"dataset": dataset, "symbol": sym, "count": len(rows), "rows": rows})
