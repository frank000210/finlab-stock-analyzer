"""Risk control API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


class NotifyReq(BaseModel):
    message: str


@router.post("/notify")
async def notify(req: NotifyReq):
    """把前端組好的風險摘要透過 Telegram 推播（需設定 TELEGRAM_BOT_TOKEN/CHAT_ID）。"""
    from ..config.settings import get_settings
    from ..notify.telegram import send_telegram

    s = get_settings()
    token = (s.telegram_bot_token or "").strip()
    chat = (s.telegram_chat_id or "").strip()
    if not token or not chat:
        return {"success": True, "sent": False, "error": "未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"}
    msg = (req.message or "").strip()[:3500]
    if not msg:
        raise HTTPException(status_code=400, detail="訊息為空")
    try:
        ok = await send_telegram(msg, token, chat)
        return {"success": True, "sent": bool(ok), "error": "" if ok else "Telegram 回應非 200"}
    except Exception as exc:  # noqa: BLE001
        return {"success": True, "sent": False, "error": str(exc)[:200]}


@router.get("/market-regime")
async def market_regime():
    """市場體制（B5）：以 0050 為大盤代理，判定 進攻/中性/防守 並給風險係數。

    規則（指數層級，非個股）：
    - 收盤 > 年線(MA200) 且年線上揚 → offense（風險係數 1.0）
    - 收盤 < 年線 且年線下彎     → defense（0.5）
    - 其他                        → neutral（0.7）
    結果快取 30 分鐘以節省資料源額度。
    """
    import math
    from datetime import date, timedelta

    from ..crawler.stock_price import StockPriceCrawler
    from ..db.memcache import mem_get, mem_set

    cache_key = "risk:market-regime"
    cached = mem_get(cache_key)
    if cached is not None:
        return {"success": True, "data": cached}

    end = date.today()
    start = end - timedelta(days=420)
    try:
        df = await StockPriceCrawler().get_price("0050", start.isoformat(), end.isoformat(), "1d")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"大盤代理資料取得失敗：{exc}")
    if df is None or df.empty or len(df) < 220:
        raise HTTPException(status_code=404, detail="大盤代理資料不足（需 220 個交易日）")

    closes = df.sort_values("date")["close"].astype(float).tolist()
    close = closes[-1]
    ma200 = sum(closes[-200:]) / 200
    ma200_prev = sum(closes[-220:-20]) / 200
    mom20 = close / closes[-21] - 1 if len(closes) >= 21 and closes[-21] else 0.0
    if any(math.isnan(x) for x in (close, ma200, ma200_prev)):
        raise HTTPException(status_code=404, detail="大盤代理資料異常")

    above, rising = close > ma200, ma200 > ma200_prev
    if above and rising:
        regime, label, mult = "offense", "進攻", 1.0
    elif not above and not rising:
        regime, label, mult = "defense", "防守", 0.5
    else:
        regime, label, mult = "neutral", "中性", 0.7

    data = {
        "regime": regime,
        "label": label,
        "risk_mult": mult,
        "proxy": "0050",
        "close": round(close, 2),
        "ma200": round(ma200, 2),
        "above_ma200": above,
        "ma200_rising": rising,
        "mom20_pct": round(mom20 * 100, 2),
        "as_of": str(df.sort_values("date")["date"].iloc[-1])[:10],
    }
    mem_set(cache_key, data, ttl_seconds=1800)
    return {"success": True, "data": data}


class SyncWatchlistReq(BaseModel):
    symbols: list[str]


@router.post("/sync-watchlist")
async def sync_watchlist(req: SyncWatchlistReq):
    """把前端觀察清單同步到後端（C9）：收盤排程掃描/推播需要知道要掃哪些。"""
    from ..data.us_symbols import normalize_symbol
    from ..db.cache import set_setting

    seen: set[str] = set()
    syms = []
    for s in req.symbols:
        u = normalize_symbol(s)
        if u and u not in seen:
            seen.add(u)
            syms.append(u)
    syms = syms[:30]
    await set_setting("alert_symbols", syms)
    return {"success": True, "data": {"count": len(syms)}}


async def build_daily_brief() -> dict:
    """盤後日報（C9/E14 共用）：市場體制 + 觀察清單 Top 設定 + 警示 tag。"""
    from ..db.cache import get_setting

    syms = await get_setting("alert_symbols", []) or []
    if not syms:
        return {"text": "", "count": 0, "note": "尚未同步觀察清單（開一次作戰台即會自動同步）"}

    regime_data = None
    try:
        regime_data = (await market_regime())["data"]
    except Exception:
        pass

    resp = await watchlist_signals(symbols=",".join(syms), lookback_days=120)
    items = [i for i in resp["data"]["items"] if i.get("ok")]
    as_of = resp["data"].get("as_of", "")

    lines = [f"📋 盤後日報 {as_of}"]
    if regime_data:
        lines.append(f"市場體制：{regime_data['label']}（風險係數 ×{regime_data['risk_mult']}，0050 {regime_data['close']} vs 年線 {regime_data['ma200']}）")
    top = [i for i in items if i.get("setup_total") is not None][:3]
    if top:
        lines.append("今日最佳設定：")
        for rank, i in enumerate(top, 1):
            nm = f" {i['name']}" if i.get("name") else ""
            lines.append(f"{rank}. {i['symbol']}{nm} {i['setup_total']}分 {i.get('trend', '')} {i['chg_pct']:+}%")
    warn_lines = []
    for i in items:
        hot = [t["t"] for t in i.get("tags", []) if t.get("tone") in ("warn", "down")]
        if hot:
            nm = f" {i['name']}" if i.get("name") else ""
            warn_lines.append(f"⚠ {i['symbol']}{nm}：{'、'.join(hot[:3])}")
    if warn_lines:
        lines.append("注意：")
        lines.extend(warn_lines[:8])
    lines.append("（僅為訊號摘要，非投資建議）")
    return {"text": "\n".join(lines)[:3500], "count": len(items), "as_of": as_of}


async def send_daily_brief() -> dict:
    """產生日報並推播 Telegram（scheduler 與手動端點共用）。"""
    from ..config.settings import get_settings
    from ..notify.telegram import send_telegram

    brief = await build_daily_brief()
    if not brief.get("text"):
        return {"sent": False, "error": brief.get("note", "無內容"), **brief}
    s = get_settings()
    token = (s.telegram_bot_token or "").strip()
    chat = (s.telegram_chat_id or "").strip()
    if not token or not chat:
        return {"sent": False, "error": "未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID", **brief}
    try:
        ok = await send_telegram(brief["text"], token, chat)
        return {"sent": bool(ok), "error": "" if ok else "Telegram 回應非 200", **brief}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "error": str(exc)[:200], **brief}


@router.get("/daily-brief")
async def daily_brief():
    """盤後日報（隨叫隨到版；排程版由 scheduler 於收盤後自動推播）。"""
    try:
        return {"success": True, "data": await build_daily_brief()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"日報產生失敗：{exc}")


@router.post("/daily-brief/send")
async def daily_brief_send():
    """手動觸發：產生日報並推播 Telegram。"""
    try:
        return {"success": True, "data": await send_daily_brief()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"日報推播失敗：{exc}")


_MAX_PRICE_ALERTS = 50


class PriceAlertReq(BaseModel):
    symbol: str
    direction: str  # "above" | "below"
    target_price: float
    note: str = ""


async def run_alert_check() -> dict:
    """檢查所有啟用中的價格警報（C10）：現價觸及設定門檻就推播 Telegram 並標記
    已觸發（一次性，不會每次檢查都重複推播）。排程與手動端點共用同一份邏輯。
    """
    import asyncio
    from datetime import date, datetime, timedelta

    from ..config.settings import get_settings
    from ..crawler.stock_price import StockPriceCrawler
    from ..data.us_symbols import normalize_symbol
    from ..db.cache import get_setting, set_setting
    from ..notify.telegram import send_telegram

    alerts = await get_setting("price_alerts", []) or []
    active = [a for a in alerts if a.get("active") and not a.get("triggered")]
    if not active:
        return {"checked": 0, "triggered": 0}

    symbols = sorted(set(normalize_symbol(a["symbol"]) for a in active))
    crawler = StockPriceCrawler()
    end = date.today()
    start = end - timedelta(days=10)

    # P3：跟 watchlist_signals/portfolio_correlation 一樣改併發抓取——最多 50
    # 檔警報若序列抓取會拖到 10-30 秒，排程每 20 分鐘跑一次也拖累其他請求。
    async def _fetch_price(sym: str):
        try:
            df = await crawler.get_price(sym, start.isoformat(), end.isoformat(), "1d")
            if df is not None and not df.empty:
                return sym, float(df.sort_values("date")["close"].iloc[-1])
        except Exception:
            pass
        return sym, None

    results = await asyncio.gather(*[_fetch_price(sym) for sym in symbols])
    prices: dict[str, float] = {sym: p for sym, p in results if p is not None}

    s = get_settings()
    token = (s.telegram_bot_token or "").strip()
    chat = (s.telegram_chat_id or "").strip()

    now_iso = datetime.utcnow().isoformat()
    triggered_count = 0
    for a in alerts:
        if not a.get("active") or a.get("triggered"):
            continue
        price = prices.get(normalize_symbol(a["symbol"]))
        if price is None:
            continue
        a["last_price"] = price
        a["last_checked_at"] = now_iso
        hit = (
            (a["direction"] == "above" and price >= a["target_price"])
            or (a["direction"] == "below" and price <= a["target_price"])
        )
        if hit:
            a["triggered"] = True
            a["triggered_at"] = now_iso
            triggered_count += 1
            if token and chat:
                dir_label = "漲破" if a["direction"] == "above" else "跌破"
                msg = f"🔔 價格警報：{a['symbol']} 已{dir_label} {a['target_price']}（現價 {price}）"
                if a.get("note"):
                    msg += f"\n備註：{a['note']}"
                try:
                    await send_telegram(msg, token, chat)
                except Exception:
                    pass
    await set_setting("price_alerts", alerts)
    return {"checked": len(symbols), "triggered": triggered_count}


@router.get("/alerts")
async def list_alerts():
    """列出所有價格警報（含最後檢查價格與觸發狀態）。"""
    from ..db.cache import get_setting

    alerts = await get_setting("price_alerts", []) or []
    return {"success": True, "data": {"items": alerts}}


@router.post("/alerts")
async def create_alert(req: PriceAlertReq):
    """新增一筆價格警報：漲破/跌破指定價位就推播 Telegram。"""
    import uuid
    from datetime import datetime

    from ..data.us_symbols import normalize_symbol
    from ..db.cache import get_setting, set_setting

    direction = req.direction.strip().lower()
    if direction not in ("above", "below"):
        raise HTTPException(status_code=400, detail="direction 必須是 above 或 below")
    if req.target_price <= 0:
        raise HTTPException(status_code=400, detail="目標價必須大於 0")
    symbol = normalize_symbol(req.symbol)
    if not symbol:
        raise HTTPException(status_code=400, detail="請提供股票代碼")

    alerts = await get_setting("price_alerts", []) or []
    if len(alerts) >= _MAX_PRICE_ALERTS:
        raise HTTPException(status_code=400, detail=f"警報數量已達上限（{_MAX_PRICE_ALERTS} 筆），請先刪除不需要的警報")

    alert = {
        "id": uuid.uuid4().hex[:12],
        "symbol": symbol,
        "direction": direction,
        "target_price": req.target_price,
        "note": req.note.strip()[:200],
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
        "triggered": False,
        "triggered_at": None,
        "last_price": None,
        "last_checked_at": None,
    }
    alerts.append(alert)
    await set_setting("price_alerts", alerts)
    return {"success": True, "data": alert}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """刪除一筆價格警報。"""
    from ..db.cache import get_setting, set_setting

    alerts = await get_setting("price_alerts", []) or []
    remaining = [a for a in alerts if a.get("id") != alert_id]
    if len(remaining) == len(alerts):
        raise HTTPException(status_code=404, detail="警報不存在")
    await set_setting("price_alerts", remaining)
    return {"success": True}


@router.post("/alerts/check")
async def check_alerts_now():
    """手動立即檢查所有警報（排程也是呼叫同一份邏輯，預設每 20 分鐘於盤中執行）。"""
    try:
        return {"success": True, "data": await run_alert_check()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"警報檢查失敗：{exc}")


async def _market_cap_tier(symbol: str, price: float, start_iso: str, end_iso: str) -> tuple[float | None, str | None]:
    """O1：市值＝現價×已發行股數，NT$100億分大/中型 vs 小型（P5：抽成共用
    helper，原本在 position_sizing() 跟 watchlist_signals() 各寫一份幾乎逐字
    重複的邏輯）。非台股或資料取不到時回傳 (None, None)，呼叫端不特別處理。
    """
    from ..crawler.finmind_client import FinMindClient
    from ..data.us_symbols import is_tw_symbol

    if not is_tw_symbol(symbol):
        return None, None
    try:
        sh = await FinMindClient().get_shares_outstanding(symbol, start_iso, end_iso)
        if sh is not None and not sh.empty and "NumberOfSharesIssued" in sh.columns:
            shares = float(sh.sort_values("date")["NumberOfSharesIssued"].iloc[-1])
            market_cap = price * shares
            cap_tier = "大型/中型" if market_cap >= 1e10 else "小型"
            return market_cap, cap_tier
    except Exception:
        pass
    return None, None


@router.get("/sizing/{symbol}")
async def position_sizing(
    symbol: str,
    atr_period: int = Query(default=14, ge=5, le=60),
    lookback_days: int = Query(default=120, ge=30, le=365),
):
    """部位風控試算所需的市場資料：現價、ATR 波動度與依 ATR 的停損建議。

    交易紀律先於方向：先定停損與單筆可承受風險，再回推部位大小。這裡只
    回傳客觀的價格/波動度與 ATR 停損參考，實際張數由前端依使用者輸入的
    資金與風險比例即時計算（不構成任何買賣建議）。
    """
    import math
    from datetime import date, timedelta

    import pandas as pd

    from ..crawler.finmind_client import FinMindClient
    from ..crawler.stock_price import StockPriceCrawler
    from ..data.us_symbols import normalize_symbol

    symbol = normalize_symbol(symbol)
    end = date.today()
    start = end - timedelta(days=lookback_days)

    try:
        crawler = StockPriceCrawler()
        df = await crawler.get_price(symbol, start.isoformat(), end.isoformat(), "1d")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"價格資料取得失敗：{exc}")

    if df is None or df.empty or len(df) < atr_period + 2:
        raise HTTPException(status_code=404, detail=f"{symbol} 價格資料不足，無法計算 ATR")

    df = df.sort_values("date").reset_index(drop=True)
    high, low, close = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = float(true_range.rolling(atr_period).mean().iloc[-1])
    price = float(close.iloc[-1])

    if math.isnan(atr) or math.isnan(price) or price <= 0:
        raise HTTPException(status_code=404, detail=f"{symbol} 無法計算有效的 ATR/現價")

    # --- 進場評分 (Setup Score, 0-100) ---
    setup = _setup_score(df, close, high, price, atr)

    # N3：波段濾網（200 日均線/年線）——當沖不用管這個，但波段留倉過夜，
    # 只做站上年線的股票能過濾掉結構性弱勢、容易被套牢賣壓咬住的標的。
    # 需要至少 200/220 個交易日資料，lookback_days 太短時就回傳 None，
    # 不硬湊一個不可靠的數字。
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else None
    ma200_prev = float(close.iloc[-220:-20].mean()) if len(close) >= 220 else None
    above_ma200 = bool(price > ma200) if ma200 is not None else None
    ma200_rising = bool(ma200 > ma200_prev) if (ma200 is not None and ma200_prev is not None) else None

    # O1：市值＝現價×已發行股數，只做一般參考資訊用（判斷這檔股票規模大小、
    # 進而評估波動/流動性風險），不影響停損/部位試算本身。
    market_cap, cap_tier = await _market_cap_tier(symbol, price, start.isoformat(), end.isoformat())

    stop_multiples = [("積極", 1.5), ("穩健", 2.0), ("保守", 3.0)]
    suggested_stops = [
        {
            "label": label,
            "mult": mult,
            "stop_price": round(price - mult * atr, 2),
            "distance": round(mult * atr, 2),
            "distance_pct": round(mult * atr / price * 100, 2),
        }
        for label, mult in stop_multiples
    ]

    name = symbol
    industry = ""
    from ..data.us_symbols import US_SYMBOLS, is_tw_symbol

    if not is_tw_symbol(symbol):
        meta = US_SYMBOLS.get(symbol)
        if meta:
            name, industry = meta["name"], meta["industry"]
    else:
        try:
            info = await FinMindClient().get_stock_info()
            if info is not None and not info.empty:
                row = info[info["stock_id"] == symbol]
                if not row.empty:
                    r0 = row.iloc[0]
                    name = str(r0.get("stock_name", symbol)) or symbol
                    industry = str(r0.get("industry_category", r0.get("Industry_category", "")) or "").strip()
        except Exception:
            pass

    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "name": name,
            "industry": industry or "未分類",
            "price": round(price, 2),
            "atr": round(atr, 2),
            "atr_period": atr_period,
            "atr_pct": round(atr / price * 100, 2),
            "suggested_stops": suggested_stops,
            "setup": setup,
            "ma200": round(ma200, 2) if ma200 is not None else None,
            "above_ma200": above_ma200,
            "ma200_rising": ma200_rising,
            "market_cap": round(market_cap) if market_cap is not None else None,
            "cap_tier": cap_tier,
            "as_of": str(df["date"].iloc[-1])[:10],
            "source": crawler.last_source,
        },
    }


def _setup_score(df, close, high, price, atr):
    """0–100 進場品質評分：趨勢排列(30) + 風報比(30) + 量能(20) + RSI 位置(20)。"""
    import numpy as np

    n = len(close)
    ma20 = float(close.tail(20).mean())
    ma60 = float(close.tail(60).mean()) if n >= 60 else float(close.mean())

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - 100 / (1 + rs)
    rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0

    vol = df["volume"].astype(float)
    vol_ma20 = float(vol.tail(20).mean()) if len(vol) >= 20 else float(vol.mean())
    vol_ratio = float(vol.iloc[-1]) / vol_ma20 if vol_ma20 else 1.0

    hi60 = float(high.tail(60).max())
    stop = price - 2 * atr
    risk = price - stop
    rr = (hi60 - price) / risk if risk > 0 else 0.0

    if price > ma20 and ma20 > ma60:
        trend, trend_note = 30, "多頭排列"
    elif price > ma20:
        trend, trend_note = 20, "站上 20MA"
    elif price > ma60:
        trend, trend_note = 10, "站上 60MA"
    else:
        trend, trend_note = 0, "弱勢（跌破均線）"

    rr_s = 30 if rr >= 3 else 22 if rr >= 2 else 12 if rr >= 1 else 4 if rr > 0 else 0
    vol_s = 20 if vol_ratio >= 1.5 else 14 if vol_ratio >= 1.0 else 8 if vol_ratio >= 0.7 else 4
    if 40 <= rsi <= 65:
        rsi_s = 20
    elif 30 <= rsi <= 70:
        rsi_s = 12
    elif rsi > 70:
        rsi_s = 4
    else:
        rsi_s = 8

    total = int(trend + rr_s + vol_s + rsi_s)
    verdict = "進場條件佳" if total >= 70 else ("普通，需再確認" if total >= 45 else "條件不佳，觀望")
    return {
        "total": total,
        "verdict": verdict,
        "rr": round(rr, 2),
        "target": round(hi60, 2),
        "components": [
            {"name": "趨勢排列", "score": trend, "max": 30, "note": trend_note},
            {"name": "風報比", "score": rr_s, "max": 30, "note": f"2×ATR 停損、波段高為目標，R:R≈{round(rr, 2)}"},
            {"name": "量能", "score": vol_s, "max": 20, "note": f"{round(vol_ratio, 2)}× 20日均量"},
            {"name": "RSI 位置", "score": rsi_s, "max": 20, "note": f"RSI {round(rsi, 1)}"},
        ],
    }


@router.get("/correlation")
async def portfolio_correlation(
    symbols: str = Query(..., description="逗號分隔股票代碼，例如 2330,2454,2882"),
    lookback_days: int = Query(default=90, ge=20, le=365),
    high_threshold: float = Query(default=0.7, ge=0.0, le=1.0),
):
    """投組相關性：以日報酬計算兩兩 Pearson 相關矩陣，標出高相關對。

    產業分類抓不到的「隱性同一注」——不同產業卻高度連動的部位——靠這個
    相關矩陣才看得出來（非投資建議）。
    """
    import asyncio
    from datetime import date, timedelta

    import numpy as np
    import pandas as pd

    from ..crawler.stock_price import StockPriceCrawler
    from ..data.us_symbols import normalize_symbol

    seen: set[str] = set()
    syms = [
        normalize_symbol(s)
        for s in symbols.split(",")
        if s.strip() and not (normalize_symbol(s) in seen or seen.add(normalize_symbol(s)))
    ]
    if len(syms) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 檔股票才能計算相關性")

    end = date.today()
    start = end - timedelta(days=lookback_days + 15)
    crawler = StockPriceCrawler()

    async def _fetch(sym: str):
        try:
            df = await crawler.get_price(sym, start.isoformat(), end.isoformat(), "1d")
            if df is None or df.empty:
                return sym, None
            s = df.sort_values("date").set_index("date")["close"].astype(float)
            return sym, s
        except Exception:
            return sym, None

    results = await asyncio.gather(*[_fetch(s) for s in syms])
    series = {sym: s for sym, s in results if s is not None and len(s) > 5}
    valid = [s for s in syms if s in series]
    if len(valid) < 2:
        raise HTTPException(status_code=404, detail="可用價格資料不足，無法計算相關性")

    price_df = pd.DataFrame({s: series[s] for s in valid}).sort_index()
    ret = price_df.pct_change().dropna(how="any")
    if len(ret) < 5:
        raise HTTPException(status_code=404, detail="重疊交易日不足，無法計算相關性")

    corr = ret.corr()
    matrix = [[round(float(corr.loc[a, b]), 3) for b in valid] for a in valid]

    pairs = []
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            c = float(corr.iloc[i, j])
            if not np.isnan(c):
                pairs.append({"a": valid[i], "b": valid[j], "corr": round(c, 3)})
    pairs.sort(key=lambda p: abs(p["corr"]), reverse=True)
    high_pairs = [p for p in pairs if p["corr"] >= high_threshold]
    avg_abs = round(float(np.mean([abs(p["corr"]) for p in pairs])), 3) if pairs else 0.0

    return {
        "success": True,
        "data": {
            "symbols": valid,
            "matrix": matrix,
            "pairs": pairs,
            "high_pairs": high_pairs,
            "high_threshold": high_threshold,
            "avg_abs_corr": avg_abs,
            "days": int(len(ret)),
        },
    }


@router.get("/watchlist-signals")
async def watchlist_signals(
    symbols: str = Query(..., description="逗號分隔股票代碼"),
    lookback_days: int = Query(default=120, ge=60, le=365),
):
    """觀察清單每日訊號摘要：趨勢排列、RSI、量能、距波段高低、ATR 停損距離。

    只掃你的觀察清單（少量、額度可控）；把清單變成每日行動清單。非投資建議。
    """
    import asyncio
    from datetime import date, timedelta

    import numpy as np
    import pandas as pd

    from ..crawler.stock_price import StockPriceCrawler
    from ..data.us_symbols import normalize_symbol

    seen: set[str] = set()
    syms = [
        normalize_symbol(s)
        for s in symbols.split(",")
        if s.strip() and not (normalize_symbol(s) in seen or seen.add(normalize_symbol(s)))
    ]
    if not syms:
        raise HTTPException(status_code=400, detail="請提供至少 1 檔股票")
    syms = syms[:30]  # 安全上限，避免爆 FinMind 額度

    end = date.today()
    start = end - timedelta(days=lookback_days)
    crawler = StockPriceCrawler()

    # 代號→名稱 批次查表：美股用內建字典；台股用 FinMind 全市場 info
    # （模組層 5 分快取，僅 1 次呼叫）；失敗時退 Mongo raw_industry。
    from ..data.us_symbols import US_SYMBOLS, is_tw_symbol

    name_map: dict[str, str] = {s: m["name"] for s, m in US_SYMBOLS.items() if s in syms}
    tw_syms = [s for s in syms if is_tw_symbol(s)]
    if tw_syms:
        try:
            from ..crawler.finmind_client import FinMindClient

            info = await FinMindClient().get_stock_info()
            if info is not None and not info.empty:
                for _, row in info.iterrows():
                    sid = str(row.get("stock_id", "")).strip().upper()
                    nm = str(row.get("stock_name", "") or "").strip()
                    if sid and nm:
                        name_map[sid] = nm
        except Exception:
            pass
        if not any(s in name_map for s in tw_syms):
            try:
                from ..db.mongodb import get_mongodb

                mongo = await get_mongodb()
                async for doc in mongo.raw_industry.find({"symbol": {"$in": tw_syms}}, {"_id": 0}):
                    if doc.get("name_zh"):
                        name_map[doc["symbol"]] = doc["name_zh"]
            except Exception:
                pass

    async def _one(sym: str):
        try:
            df = await crawler.get_price(sym, start.isoformat(), end.isoformat(), "1d")
        except Exception:
            return {"symbol": sym, "name": name_map.get(sym, ""), "ok": False, "error": "資料取得失敗"}
        if df is None or df.empty or len(df) < 30:
            return {"symbol": sym, "name": name_map.get(sym, ""), "ok": False, "error": "資料不足"}
        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol = df["volume"].astype(float)
        price = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        chg_pct = round((price - prev) / prev * 100, 2) if prev else 0.0

        # O1：跳空缺口＝今天開盤價 vs 昨收，不是漲跌幅（收盤 vs 昨收）。
        open_today = float(df["open"].iloc[-1])
        gap_pct = round((open_today - prev) / prev * 100, 2) if prev else 0.0

        # 市值分級：大型/中型股跳空門檻低（3%），小型股天生波動大、門檻要拉高
        # （10%），不然雜訊會蓋過真訊號——直接套講者的美股門檻沒意義（她的
        # 8-10億美元對台股規模來說是極小型股），改用台股慣例的百億分界。
        market_cap, cap_tier = await _market_cap_tier(sym, price, start.isoformat(), end.isoformat())
        gap_threshold = 3.0 if cap_tier != "小型" else 10.0

        ma20 = float(close.tail(20).mean())
        ma60 = float(close.tail(60).mean()) if len(close) >= 60 else float(close.mean())

        # RSI(14)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = float((100 - 100 / (1 + rs)).iloc[-1]) if not np.isnan(rs.iloc[-1]) else 50.0

        # ATR(14) + 2xATR stop distance
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        stop_dist_pct = round(2 * atr / price * 100, 2) if price else None

        vol_ma20 = float(vol.tail(20).mean()) if len(vol) >= 20 else float(vol.mean())
        vol_ratio = round(float(vol.iloc[-1]) / vol_ma20, 2) if vol_ma20 else None

        window = close.tail(60)
        hi60, lo60 = float(window.max()), float(window.min())
        pos_pct = round((price - lo60) / (hi60 - lo60) * 100, 1) if hi60 > lo60 else 50.0

        tags = []
        if price > ma20 > ma60:
            trend = "多頭排列"; tags.append({"t": "多頭排列", "tone": "up"})
        elif price < ma20 < ma60:
            trend = "空頭排列"; tags.append({"t": "空頭排列", "tone": "down"})
        else:
            trend = "盤整"; tags.append({"t": "盤整", "tone": "flat"})
        if rsi >= 70:
            tags.append({"t": f"RSI {rsi:.0f} 超買", "tone": "down"})
        elif rsi <= 30:
            tags.append({"t": f"RSI {rsi:.0f} 超賣", "tone": "up"})
        if vol_ratio and vol_ratio >= 1.5:
            tags.append({"t": f"爆量 {vol_ratio}×", "tone": "warn"})
        if pos_pct >= 95:
            tags.append({"t": "逼近波段高", "tone": "warn"})
        elif pos_pct <= 5:
            tags.append({"t": "逼近波段低", "tone": "warn"})
        if abs(gap_pct) >= gap_threshold:
            tags.append({"t": f"跳空 {gap_pct:+.1f}%", "tone": "warn"})

        try:
            _s = _setup_score(df, close, high, price, atr)
            setup_total, setup_verdict = _s["total"], _s["verdict"]
        except Exception:
            setup_total, setup_verdict = None, ""

        return {
            "symbol": sym, "name": name_map.get(sym, ""), "ok": True, "price": round(price, 2), "chg_pct": chg_pct,
            "trend": trend, "rsi": round(rsi, 1), "stop_dist_pct": stop_dist_pct,
            "vol_ratio": vol_ratio, "range_pos_pct": pos_pct, "tags": tags,
            "setup_total": setup_total, "setup_verdict": setup_verdict,
            "gap_pct": gap_pct, "market_cap": round(market_cap) if market_cap is not None else None,
            "cap_tier": cap_tier,
        }

    items = await asyncio.gather(*[_one(s) for s in syms])
    # 有評分的排前面，並依評分由高到低（最佳設定優先）
    items.sort(key=lambda x: (x.get("setup_total") is None, -(x.get("setup_total") or 0)))
    return {"success": True, "data": {"items": items, "as_of": end.isoformat()}}
