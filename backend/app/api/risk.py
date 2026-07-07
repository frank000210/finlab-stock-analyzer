"""Risk control API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..risk import risk_manager

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


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
        df = await StockPriceCrawler().get_price(symbol, start.isoformat(), end.isoformat(), "1d")
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
            "as_of": str(df["date"].iloc[-1])[:10],
        },
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
