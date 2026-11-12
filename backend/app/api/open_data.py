"""官方開放資料倉庫 API：健康檢查、狀態、手動觸發、讀取已存資料。

- /health 與 /data 是唯讀、不用登入，也不會打任何外部來源（只讀自己的 MongoDB）。
- /status（含最近幾輪的執行紀錄與錯誤訊息）與 /run 需要管理員 token。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ..data import open_data as od
from .admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/open-data", tags=["open-data"])

_bg: set[asyncio.Task] = set()


class RunReq(BaseModel):
    datasets: Optional[list[str]] = None  # 不給＝全部
    force: bool = False  # 集保「已有最新一份就不重抓」的略過規則；不影響被擋後的冷卻


def _ok(data):
    return {"success": True, "data": jsonable_encoder(data)}


@router.get("/health")
async def health():
    """各資料集是否新鮮：ok／partial／stale／error／never。給外部監看與入口頁用。"""
    return _ok(await od.get_health())


@router.get("/status", dependencies=[Depends(require_admin)])
async def status():
    return _ok(await od.get_status())


@router.post("/run", dependencies=[Depends(require_admin)])
async def run(req: RunReq):
    """背景跑一輪，立刻回應；結果看 /status。被來源擋過會冷卻 6 小時，期間不會真的去抓。"""
    if od.is_running():
        return _ok({"started": False, "reason": "already_running"})
    if req.datasets is not None:
        bad = [d for d in req.datasets if d not in od.DATASETS]
        if bad:
            raise HTTPException(status_code=400, detail=f"未知的資料集：{','.join(bad)}")
    task = asyncio.create_task(od.run_sync(datasets=req.datasets, trigger="manual", force=req.force))
    _bg.add(task)
    task.add_done_callback(_bg.discard)
    return _ok({"started": True})


@router.get("/data/{dataset}/{symbol}")
async def read_data(
    dataset: str,
    symbol: str,
    start: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}(-\d{2})?$"),
    end: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}(-\d{2})?$"),
    limit: int = Query(default=120, ge=1, le=1000),
):
    """單一股票的已存資料（由舊到新）。日期欄位：月營收用 ym（YYYY-MM），其他用 date（YYYY-MM-DD）。"""
    spec = od.DATASETS.get(dataset)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"未知的資料集：{dataset}")
    sym = od.clean_symbol(symbol)
    if not sym:
        raise HTTPException(status_code=400, detail="代號格式不正確")
    field = spec["date_field"]
    q: dict = {"symbol": sym}
    if start or end:
        q[field] = {**({"$gte": start} if start else {}), **({"$lte": end} if end else {})}
    db = await od._db()
    rows = await db[spec["coll"]].find(q, {"_id": 0}).sort(field, -1).limit(limit).to_list(length=limit)
    rows.reverse()
    return _ok({"dataset": dataset, "symbol": sym, "count": len(rows), "rows": rows})
