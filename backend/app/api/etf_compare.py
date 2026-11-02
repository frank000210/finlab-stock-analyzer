"""ETF／個股綜合比較 API。

兩支端點：
- GET /api/v1/etf-compare/catalog  可選標的（FinMind 的 ETF 清單＋分類）與一鍵情境
- GET /api/v1/etf-compare/compare  最多 10 檔的績效、配息、填息、五維評分、急跌與反彈

所有數字由 analysis/etf_compare.py 從 FinMind 日線與除息紀錄算出；單檔結果快取 6 小時
（key 含日期，跨日自然失效），所以重複比較同一批標的不會再打 FinMind（免費額度很吃緊）。
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..analysis import etf_compare as core

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/etf-compare", tags=["etf-compare"])

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{3,8}$")
_MAX_SYMBOLS = 10
_BENCHMARK = "0050"
_HISTORY_DAYS = 2010  # ≈5.5 年：夠算 5 年走勢與 3 年 CAGR
_FETCH_CONCURRENCY = 4
# 限流（每個 IP、每 10 分鐘的固定視窗，視窗長度見 cache.CACHE_TTL["rate_limit"]）。
# 兩個獨立的額度：
# - 請求數：很寬，只擋腳本式連打。快取命中的請求不碰 FinMind，使用者重新整理、調區間都算正常使用。
# - 真正要打 FinMind 的標的數：保護免費額度。每檔 = 日線＋除息 2 次呼叫；單檔結果快取 6 小時，
#   所以同一批標的只有第一次會計。
_RATE_MAX_REQUESTS = 300
_RATE_MAX_FETCHES = 60
_BUNDLE_VERSION = "v1"  # 改了計算邏輯就加一，舊快取自然作廢
_AUTO_LOOKBACK_DEFAULT = 180
_MISS = object()

# 一鍵情境。只放「長期存在、不易下市」的標的；清單中不在 FinMind 的會被濾掉。
PRESETS = [
    {"key": "cap_vs_div", "label": "市值 vs 高股息", "symbols": ["0050", "006208", "0056", "00878", "00919", "00929"]},
    {"key": "div7", "label": "高股息 7 強", "symbols": ["0056", "00878", "00919", "00713", "00929", "00939", "00940"]},
    {"key": "active", "label": "主動型熱門", "symbols": ["00981A", "00980A", "00982A", "00400A", "00401A"]},
    {"key": "stock_vs_cap", "label": "個股 vs 市值龍頭", "symbols": ["2330", "2454", "2408", "0050"]},
]

CATEGORY_LABELS = {"market": "市值型", "dividend": "高股息", "active": "主動型", "other": "其他 ETF", "stock": "個股"}


def _too_many(seconds_left: int) -> HTTPException:
    minutes = max(1, -(-seconds_left // 60))
    return HTTPException(
        status_code=429,
        detail=f"查詢過於頻繁，請約 {minutes} 分鐘後再試。",
        headers={"Retry-After": str(max(seconds_left, 1))},
    )


async def _consume(request: Request, kind: str, cost: int, limit: int) -> None:
    """固定視窗計數；超量回 429（附剩餘秒數）。計數機制故障時放行，不擋功能。"""
    from ..api.analytics import _get_client_ip
    from ..db.cache import consume_fixed_window

    ip = _get_client_ip(request)
    if not ip or ip == "unknown":
        return
    try:
        count, left = await consume_fixed_window(f"etf_compare_{kind}:{ip}", cost)
    except Exception:
        return
    if count > limit:
        raise _too_many(left)


async def _check_request_rate(request: Request) -> None:
    await _consume(request, "req", 1, _RATE_MAX_REQUESTS)


async def _cache_get(key: str):
    try:
        from ..db.cache import get_cache

        return await get_cache(key)
    except Exception:
        return None


async def _cache_set(key: str, data) -> None:
    try:
        from ..db.cache import set_cache

        await set_cache(key, data, "etf_compare")
    except Exception:
        logger.warning("etf_compare cache write failed for %s", key)


async def _stock_info() -> dict[str, dict]:
    """{symbol: {name, industry}}，來源 TaiwanStockInfo（同一檔多列時取第一筆名稱，產業若任一列是 ETF 即 ETF）。"""
    from ..crawler.finmind_client import FinMindClient

    out: dict[str, dict] = {}
    df = await FinMindClient().get_stock_info()
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        sid = str(row.get("stock_id", "")).strip().upper()
        if not sid:
            continue
        ind = str(row.get("industry_category", row.get("Industry_category", "")) or "").strip()
        cur = out.setdefault(sid, {"name": str(row.get("stock_name", "") or "").strip(), "industry": ind})
        if ind.upper() == "ETF":
            cur["industry"] = "ETF"
    return out


def _is_etf(sid: str, meta: dict) -> bool:
    return meta.get("industry", "").upper() == "ETF" or (sid.startswith("00") and len(sid) >= 5)


def _category(sid: str, meta: dict) -> str:
    if not _is_etf(sid, meta):
        return "stock"
    return core.classify_etf(sid, meta.get("name", ""))


@router.get("/catalog", dependencies=[Depends(_check_request_rate)])
async def catalog():
    """可選標的與一鍵情境。個股不列在清單裡（太多），由前端搜尋框補。"""
    try:
        info = await _stock_info()
    except Exception as exc:
        logger.exception("etf_compare catalog: stock info failed")
        raise HTTPException(status_code=502, detail=f"標的清單查詢失敗：{exc}")
    items = []
    for sid, meta in info.items():
        if _is_etf(sid, meta):
            items.append({"symbol": sid, "name": meta["name"], "category": _category(sid, meta)})
    items.sort(key=lambda x: x["symbol"])
    presets = []
    for p in PRESETS:
        syms = [s for s in p["symbols"] if s in info]
        if len(syms) >= 2:
            presets.append({"key": p["key"], "label": p["label"], "symbols": syms})
    return {
        "success": True,
        "data": {
            "etfs": items,
            "presets": presets,
            "category_labels": CATEGORY_LABELS,
            "max_symbols": _MAX_SYMBOLS,
            "benchmark": _BENCHMARK,
        },
    }


def _parse_symbols(raw: str) -> list[str]:
    seen: list[str] = []
    for part in (raw or "").split(","):
        s = part.strip().upper()
        if not s:
            continue
        if not _SYMBOL_RE.match(s):
            raise HTTPException(status_code=400, detail=f"不支援的標的代碼格式：{part.strip()[:12]}")
        if s not in seen:
            seen.append(s)
    if not seen:
        raise HTTPException(status_code=400, detail="請至少選擇一檔標的。")
    if len(seen) > _MAX_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"一次最多比較 {_MAX_SYMBOLS} 檔。")
    return seen


def _parse_day(raw: Optional[str], label: str) -> Optional[str]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}日期格式需為 YYYY-MM-DD。")


def _bundle_key(symbol: str) -> str:
    return f"etf_compare:{_BUNDLE_VERSION}:{symbol}:{date.today().isoformat()}"


async def _load_bundle(symbol: str, sem: asyncio.Semaphore, cached=_MISS) -> Optional[dict]:
    """單檔：先查快取，沒有才打 FinMind（日線＋除息結果）並整理。無資料回 None。

    cached 給呼叫端已經查過快取時帶進來（None＝沒命中），避免同一個 key 讀兩次。
    """
    key = _bundle_key(symbol)
    if cached is _MISS:
        cached = await _cache_get(key)
    if cached:
        return cached if cached.get("ok") else None

    from ..crawler.finmind_client import FinMindClient

    start = (date.today() - timedelta(days=_HISTORY_DAYS)).isoformat()
    end = date.today().isoformat()
    client = FinMindClient()
    async with sem:
        price_df = await client.get_stock_price(symbol, start, end)
        try:
            div_df = await client.get_dividend_result(symbol, start, end)
        except Exception:
            # 除息資料取不到時，仍可用價格算績效；殖利率與填息會顯示「資料不足」
            logger.warning("etf_compare: dividend result failed for %s", symbol)
            div_df = None

    if price_df is None or price_df.empty:
        await _cache_set(key, {"ok": False})
        return None
    price_rows = price_df.assign(date=price_df["date"].dt.strftime("%Y-%m-%d")).to_dict("records")
    div_rows = div_df.to_dict("records") if div_df is not None and not div_df.empty else []
    bundle = core.build_symbol_bundle(price_rows, div_rows)
    if bundle is None:
        await _cache_set(key, {"ok": False})
        return None
    bundle["ok"] = True
    await _cache_set(key, bundle)
    return bundle


@router.get("/compare", dependencies=[Depends(_check_request_rate)])
async def compare(
    request: Request,
    symbols: str = Query(..., description="以逗號分隔的標的代碼，最多 10 檔"),
    event_start: Optional[str] = Query(None, description="急跌區間起日（YYYY-MM-DD），不給則自動偵測"),
    event_end: Optional[str] = Query(None, description="急跌區間迄日（YYYY-MM-DD）"),
    auto_lookback: int = Query(_AUTO_LOOKBACK_DEFAULT, ge=30, le=730, description="自動偵測：往回看幾天（預設 180）"),
    auto_anchor: Optional[str] = Query(None, description="自動偵測：用哪一檔找急跌區間，預設 0050；需是已選標的之一"),
):
    syms = _parse_symbols(symbols)
    ev_start, ev_end = _parse_day(event_start, "起"), _parse_day(event_end, "迄")
    if bool(ev_start) != bool(ev_end):
        raise HTTPException(status_code=400, detail="急跌區間需同時提供起日與迄日。")
    if ev_start and (ev_start >= ev_end or (date.fromisoformat(ev_end) - date.fromisoformat(ev_start)).days > 400):
        raise HTTPException(status_code=400, detail="急跌區間需起日早於迄日，且不超過 400 天。")
    anchor = (auto_anchor or "").strip().upper() or _BENCHMARK
    if not _SYMBOL_RE.match(anchor) or (anchor != _BENCHMARK and anchor not in syms):
        raise HTTPException(status_code=400, detail=f"自動偵測的基準需是已選標的之一或 {_BENCHMARK}。")

    sem = asyncio.Semaphore(_FETCH_CONCURRENCY)
    # 自訂區間不需要基準；自動偵測才要（基準不在已選標的裡時才多載一檔）
    need = list(syms) + ([anchor] if not ev_start and anchor not in syms else [])
    # 先看快取：全部命中就不計 FinMind 額度（使用者重新整理、調區間都不該被擋）
    cached = await asyncio.gather(*[_cache_get(_bundle_key(s)) for s in need])
    misses = sum(1 for c in cached if not c)
    if misses:
        await _consume(request, "fetch", misses, _RATE_MAX_FETCHES)
    try:
        results = await asyncio.gather(*[_load_bundle(s, sem, c) for s, c in zip(need, cached)], return_exceptions=True)
    except Exception as exc:  # pragma: no cover - gather(return_exceptions) 不會丟
        logger.exception("etf_compare: gather failed")
        raise HTTPException(status_code=502, detail=f"資料查詢失敗：{exc}")
    bundles: dict[str, Optional[dict]] = {}
    errors: dict[str, str] = {}
    for s, r in zip(need, results):
        if isinstance(r, Exception):
            logger.error("etf_compare: load failed for %s: %s", s, type(r).__name__)
            errors[s] = "資料來源暫時無法取得"
            bundles[s] = None
        else:
            bundles[s] = r

    if all(bundles.get(s) is None for s in syms):
        # 全數失敗：多半是資料源問題，給 502 而不是一個空頁面
        raise HTTPException(status_code=502, detail="所選標的都查不到日線資料，請稍後再試。")

    try:
        info = await _stock_info()
    except Exception:
        logger.warning("etf_compare: stock info unavailable, names omitted")
        info = {}

    # 事件視窗：使用者指定優先，否則用基準（預設 0050）偵測最近一次明顯急跌
    event = None
    if ev_start:
        event = {"start": ev_start, "end": ev_end, "source": "custom", "drop": None}
    elif bundles.get(anchor):
        ep = core.bundle_drawdown_episode(bundles[anchor], lookback_days=auto_lookback)
        if ep:
            event = {"start": ep["start"], "end": ep["end"], "source": "auto", "drop": ep["drop"],
                     "anchor": anchor, "lookback_days": auto_lookback}

    out_symbols, failed = [], []
    for s in syms:
        b = bundles.get(s)
        meta = info.get(s, {})
        if b is None:
            failed.append({"symbol": s, "name": meta.get("name", ""),
                           "reason": errors.get(s, "查無日線資料（代碼錯誤或尚未上市）")})
            continue
        item = {
            "symbol": s,
            "name": meta.get("name", ""),
            "category": _category(s, meta),
            "metrics": b["metrics"],
            "dividends": b["dividends"],
            "fill": b["fill"],
            "scores": b["scores"],
            "series": b["series"],
            "splits": b.get("splits", []),
            "event": core.bundle_event(b, event["start"], event["end"]) if event else None,
        }
        out_symbols.append(item)

    asof = max((it["metrics"].get("last_date", "") for it in out_symbols), default="")
    return {
        "success": True,
        "data": {
            "asof": asof,
            "symbols": out_symbols,
            "failed": failed,
            "event": event,
            "method": {
                "risk_free": core.RISK_FREE_RATE,
                "min_stats_days": core.MIN_STATS_DAYS,
                "fill_window_days": core.FILL_WINDOW_DAYS,
                "fill_lookback_years": core.FILL_LOOKBACK_YEARS,
            },
        },
    }
