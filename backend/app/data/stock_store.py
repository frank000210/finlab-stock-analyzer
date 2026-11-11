"""每日資料庫：把白名單股票的相關資訊「增量」寫進 MongoDB。

做法
- 每個資料集一個 collection（md_price / md_institutional / md_margin / md_valuation / md_revenue），
  以 (symbol, date[, name]) 為唯一鍵 upsert，重複抓不會產生重複資料。
- md_state 記每檔股票、每個資料集「目前存到哪一天」。下次只抓 last_date 之後的資料
  （往前多抓幾天重疊，吃掉盤後更正；月營收重疊較久，因為公布有時間差）。第一次才回補歷史。
- 白名單存在 settings 集合（key=stock_store_whitelist），沒設定時才用環境變數 STOCK_STORE_SYMBOLS。
- 排程（15:00 台灣時間、平日）與手動觸發都走 run_sync；同時只會有一個 run 在跑。
- FinMind 免費額度用完（HTTP 402/403/429）就立刻停止這一輪，已存的不受影響，下一輪從斷點接續。

純函式（plan_start、normalize_symbols、rows_to_docs）不碰網路與資料庫，方便單元測試；
run_sync 的 db 與抓取函式可注入，測試用假的。
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

WHITELIST_KEY = "stock_store_whitelist"
MAX_SYMBOLS = 100  # 免費額度每小時 600 次；每檔 × 5 個資料集，白名單上限抓 100 檔已偏多
_SYMBOL_RE = re.compile(r"^[0-9A-Z]{4,6}$")
_QUOTA_RE = re.compile(r"HTTP (402|403|429)|upper limit|rate limit|limit", re.IGNORECASE)
CALL_PAUSE_SEC = 0.25
CALL_TIMEOUT_SEC = 60

# 每個資料集：collection、唯一鍵、第一次回補天數、往前重疊天數、FinMindClient 的方法名
DATASETS: dict[str, dict[str, Any]] = {
    "price": {"coll": "md_price", "keys": ("symbol", "date"), "backfill": 400, "overlap": 3, "method": "get_stock_price", "label": "日 K"},
    "institutional": {"coll": "md_institutional", "keys": ("symbol", "date", "name"), "backfill": 180, "overlap": 3, "method": "get_institutional_investors", "label": "三大法人"},
    "margin": {"coll": "md_margin", "keys": ("symbol", "date"), "backfill": 180, "overlap": 3, "method": "get_margin_trading", "label": "融資融券"},
    "valuation": {"coll": "md_valuation", "keys": ("symbol", "date"), "backfill": 400, "overlap": 3, "method": "get_valuation", "label": "本益比／淨值比"},
    "revenue": {"coll": "md_revenue", "keys": ("symbol", "date"), "backfill": 800, "overlap": 45, "method": "get_monthly_revenue", "label": "月營收"},
}
STATE_COLL = "md_state"
RUNS_COLL = "md_runs"

_run_lock = asyncio.Lock()
_running = False


# ───────────────────────── 純函式 ─────────────────────────

def normalize_symbols(raw: Any, limit: int = MAX_SYMBOLS) -> list[str]:
    """清單或逗號字串 → 大寫、去重、保序的合法代號；超過上限或有非法代號時丟 ValueError。"""
    if raw is None:
        return []
    items = re.split(r"[,\s]+", raw) if isinstance(raw, str) else list(raw)
    out: list[str] = []
    for item in items:
        s = str(item).strip().upper()
        if not s:
            continue
        if not _SYMBOL_RE.match(s):
            raise ValueError(f"代號格式不正確：{s}（需為 4～6 碼英數字）")
        if s not in out:
            out.append(s)
    if len(out) > limit:
        raise ValueError(f"白名單最多 {limit} 檔，目前 {len(out)} 檔")
    return out


def plan_start(last_date: Optional[str], today: date, backfill_days: int, overlap_days: int) -> str:
    """這次該從哪一天開始抓。沒存過 → 往前回補 backfill_days；存過 → 從 last_date 往前重疊 overlap_days。"""
    if not last_date:
        return (today - timedelta(days=backfill_days)).isoformat()
    try:
        last = date.fromisoformat(str(last_date)[:10])
    except ValueError:
        return (today - timedelta(days=backfill_days)).isoformat()
    start = last - timedelta(days=overlap_days)
    return min(start, today).isoformat()


def _clean(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):  # numpy 純量
        try:
            return _clean(v.item())
        except Exception:  # noqa: BLE001
            return None
    return v


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    s = str(v)[:10]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


def rows_to_docs(dataset: str, symbol: str, records: list[dict], now: datetime) -> list[dict]:
    """FinMind 回傳的列 → 要 upsert 的文件。沒有合法日期的列丟掉；institutional 另需 name。"""
    spec = DATASETS[dataset]
    docs: list[dict] = []
    for rec in records:
        iso = _iso(rec.get("date"))
        if not iso:
            continue
        doc = {k: _clean(v) for k, v in rec.items() if k not in ("stock_id", "date")}
        doc["symbol"] = symbol
        doc["date"] = iso
        doc["updated_at"] = now
        if "name" in spec["keys"] and not doc.get("name"):
            continue
        docs.append(doc)
    return docs


def is_quota_error(exc: BaseException) -> bool:
    return bool(_QUOTA_RE.search(str(exc)))


# ───────────────────────── 資料庫存取 ─────────────────────────

async def _db():
    from ..db.mongodb import get_mongodb

    return await get_mongodb()


async def ensure_indexes(db=None) -> None:
    db = db if db is not None else await _db()
    for spec in DATASETS.values():
        await db[spec["coll"]].create_index([(k, 1) for k in spec["keys"]], unique=True)
    await db[STATE_COLL].create_index([("symbol", 1), ("dataset", 1)], unique=True)
    await db[RUNS_COLL].create_index([("started_at", -1)])


async def get_whitelist(db=None) -> dict[str, Any]:
    """{'symbols': [...], 'source': 'db'|'env'|'none'}。資料庫有設定（含空清單）就以資料庫為準。"""
    db = db if db is not None else await _db()
    doc = await db.settings.find_one({"key": WHITELIST_KEY})
    if doc is not None and isinstance(doc.get("value"), list):
        return {"symbols": normalize_symbols(doc["value"]), "source": "db"}
    env = os.getenv("STOCK_STORE_SYMBOLS", "").strip()
    if env:
        try:
            return {"symbols": normalize_symbols(env), "source": "env"}
        except ValueError:
            logger.warning("STOCK_STORE_SYMBOLS 內容不合法，忽略")
    return {"symbols": [], "source": "none"}


async def set_whitelist(symbols: Any, db=None) -> list[str]:
    cleaned = normalize_symbols(symbols)
    db = db if db is not None else await _db()
    await db.settings.update_one(
        {"key": WHITELIST_KEY},
        {"$set": {"key": WHITELIST_KEY, "value": cleaned, "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return cleaned


async def _upsert(coll, keys: tuple, docs: list[dict]) -> int:
    from pymongo import UpdateOne

    if not docs:
        return 0
    ops = [UpdateOne({k: d.get(k) for k in keys}, {"$set": d}, upsert=True) for d in docs]
    await coll.bulk_write(ops, ordered=False)
    return len(docs)


Fetcher = Callable[[str, str, str], Awaitable[Any]]  # (symbol, start, end) -> DataFrame


def default_fetchers() -> dict[str, Fetcher]:
    from ..crawler.finmind_client import FinMindClient

    client = FinMindClient()
    return {ds: getattr(client, spec["method"]) for ds, spec in DATASETS.items()}


async def sync_one(
    db, fetch: Fetcher, dataset: str, symbol: str, today: date, now: Optional[datetime] = None
) -> dict[str, Any]:
    """同步單一（股票, 資料集）。回傳 {rows, start, last_date, error}；額度用完會往外丟。"""
    spec = DATASETS[dataset]
    now = now or datetime.utcnow()
    state = await db[STATE_COLL].find_one({"symbol": symbol, "dataset": dataset}) or {}
    start = plan_start(state.get("last_date"), today, spec["backfill"], spec["overlap"])
    result: dict[str, Any] = {"dataset": dataset, "symbol": symbol, "start": start, "rows": 0, "last_date": state.get("last_date"), "error": None}
    try:
        df = await asyncio.wait_for(fetch(symbol, start, today.isoformat()), timeout=CALL_TIMEOUT_SEC)
        records = [] if df is None or getattr(df, "empty", False) else df.to_dict("records")
        docs = rows_to_docs(dataset, symbol, records, now)
        result["rows"] = await _upsert(db[spec["coll"]], spec["keys"], docs)
        if docs:
            result["last_date"] = max(d["date"] for d in docs)
        new_state = {"symbol": symbol, "dataset": dataset, "last_date": result["last_date"], "last_run": now, "last_error": None}
    except Exception as exc:  # noqa: BLE001
        if is_quota_error(exc):
            raise
        logger.warning("stock_store: %s/%s 失敗：%s", symbol, dataset, exc)
        result["error"] = str(exc)[:200]
        new_state = {"symbol": symbol, "dataset": dataset, "last_date": state.get("last_date"), "last_run": now, "last_error": result["error"]}
    await db[STATE_COLL].update_one({"symbol": symbol, "dataset": dataset}, {"$set": new_state}, upsert=True)
    return result


def is_running() -> bool:
    return _running


async def run_sync(
    symbols: Optional[list[str]] = None,
    datasets: Optional[list[str]] = None,
    trigger: str = "schedule",
    db=None,
    fetchers: Optional[dict[str, Fetcher]] = None,
    today: Optional[date] = None,
    pause: float = CALL_PAUSE_SEC,
) -> dict[str, Any]:
    """跑一輪增量同步。symbols 不給就用白名單。同時只允許一輪；已有一輪在跑回傳 skipped。"""
    global _running
    if _run_lock.locked():
        return {"skipped": "already_running"}
    async with _run_lock:
        _running = True
        started = datetime.utcnow()
        try:
            db = db if db is not None else await _db()
            await ensure_indexes(db)
            syms = normalize_symbols(symbols) if symbols is not None else (await get_whitelist(db))["symbols"]
            ds_list = [d for d in (datasets or list(DATASETS)) if d in DATASETS]
            summary: dict[str, Any] = {
                "trigger": trigger, "started_at": started, "symbols": len(syms), "datasets": ds_list,
                "rows": 0, "errors": 0, "aborted": None, "per_symbol": {},
            }
            if not syms:
                summary["note"] = "白名單是空的，沒有要抓的股票"
            fetchers = fetchers or (default_fetchers() if syms else {})
            today = today or date.today()
            try:
                for sym in syms:
                    per = {"rows": 0, "errors": 0}
                    summary["per_symbol"][sym] = per
                    for ds in ds_list:
                        r = await sync_one(db, fetchers[ds], ds, sym, today)
                        per["rows"] += r["rows"]
                        if r["error"]:
                            per["errors"] += 1
                            summary["errors"] += 1
                        summary["rows"] += r["rows"]
                        if pause:
                            await asyncio.sleep(pause)
            except Exception as exc:  # noqa: BLE001  額度用完：停這一輪，下一輪接續
                if not is_quota_error(exc):
                    raise
                summary["aborted"] = "quota"
                logger.warning("stock_store: FinMind 額度用完，這一輪提早結束（%s）", exc)
            summary["finished_at"] = datetime.utcnow()
            await db[RUNS_COLL].insert_one(dict(summary))
            old = await db[RUNS_COLL].find({}, {"_id": 1}).sort("started_at", -1).skip(30).to_list(length=None)
            if old:
                await db[RUNS_COLL].delete_many({"_id": {"$in": [o["_id"] for o in old]}})
            logger.info("stock_store: %s 完成 symbols=%d rows=%d errors=%d aborted=%s", trigger, len(syms), summary["rows"], summary["errors"], summary["aborted"])
            return summary
        finally:
            _running = False


async def get_status(db=None) -> dict[str, Any]:
    db = db if db is not None else await _db()
    wl = await get_whitelist(db)
    states = await db[STATE_COLL].find({"symbol": {"$in": wl["symbols"]}}, {"_id": 0}).to_list(length=None) if wl["symbols"] else []
    by_symbol: dict[str, dict] = {s: {} for s in wl["symbols"]}
    for st in states:
        by_symbol.setdefault(st["symbol"], {})[st["dataset"]] = {
            "last_date": st.get("last_date"), "last_run": st.get("last_run"), "last_error": st.get("last_error"),
        }
    runs = await db[RUNS_COLL].find({}, {"_id": 0, "per_symbol": 0}).sort("started_at", -1).limit(5).to_list(length=5)
    counts = {}
    for ds, spec in DATASETS.items():
        counts[ds] = await db[spec["coll"]].count_documents({})
    return {
        "whitelist": wl, "running": _running, "datasets": {k: v["label"] for k, v in DATASETS.items()},
        "stored_counts": counts, "symbols": by_symbol, "recent_runs": runs, "max_symbols": MAX_SYMBOLS,
    }
