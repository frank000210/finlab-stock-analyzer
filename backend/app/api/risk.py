"""Risk control API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..risk import risk_manager

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
    from ..db.cache import set_setting

    seen: set[str] = set()
    syms = []
    for s in req.symbols:
        u = str(s or "").strip().upper()
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


@router.get("/status")
async def get_risk_status():
    try:
        return {"success": True, "data": risk_manager.get_status().model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/equity-curve")
async def get_equity_curve(hours: int = Query(default=30, ge=1, le=720)):
    try:
        points = risk_manager.get_equity_curve(hours=hours)
        return {
            "success": True,
            "data": {
                "items": [point.model_dump() for point in points],
                # See risk/manager.py module docstring: this curve is a
                # simulated pseudo-random walk, not a real equity history.
                "is_simulated": True,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker():
    try:
        status = risk_manager.reset_circuit_breaker()
        return {"success": True, "data": status.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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

    symbol = symbol.strip().upper()
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

    seen: set[str] = set()
    syms = [
        s.strip().upper()
        for s in symbols.split(",")
        if s.strip() and not (s.strip().upper() in seen or seen.add(s.strip().upper()))
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

    seen: set[str] = set()
    syms = [
        s.strip().upper()
        for s in symbols.split(",")
        if s.strip() and not (s.strip().upper() in seen or seen.add(s.strip().upper()))
    ]
    if not syms:
        raise HTTPException(status_code=400, detail="請提供至少 1 檔股票")
    syms = syms[:30]  # 安全上限，避免爆 FinMind 額度

    end = date.today()
    start = end - timedelta(days=lookback_days)
    crawler = StockPriceCrawler()

    # 代號→名稱 批次查表：FinMind 全市場 info（模組層 5 分快取，僅 1 次呼叫）；
    # 失敗時退 Mongo raw_industry（關聯圖 ingest 累積的名稱），再不行就只給代號。
    name_map: dict[str, str] = {}
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
    if not name_map:
        try:
            from ..db.mongodb import get_mongodb

            mongo = await get_mongodb()
            async for doc in mongo.raw_industry.find({"symbol": {"$in": syms}}, {"_id": 0}):
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
        }

    items = await asyncio.gather(*[_one(s) for s in syms])
    # 有評分的排前面，並依評分由高到低（最佳設定優先）
    items.sort(key=lambda x: (x.get("setup_total") is None, -(x.get("setup_total") or 0)))
    return {"success": True, "data": {"items": items, "as_of": end.isoformat()}}
