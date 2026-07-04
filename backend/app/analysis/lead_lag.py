"""Lead-Lag analysis: compare stock movements against market/sector leaders.

Uses cross-correlation of daily returns to determine if a stock leads or
lags the benchmark (TAIEX index or a sector leader), and by how many days.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional
from ..crawler import StockPriceCrawler, FinMindClient
from .correlation import cross_corr_at_lag, safe_corr


# Major sector leaders for reference
SECTOR_LEADERS = {
    "半導體": {"symbol": "2330", "name": "台積電"},
    "金融": {"symbol": "2882", "name": "國泰金"},
    "電子": {"symbol": "2317", "name": "鴻海"},
    "傳產": {"symbol": "1301", "name": "台塑"},
    "航運": {"symbol": "2603", "name": "長榮"},
    "鋼鐵": {"symbol": "2002", "name": "中鋼"},
    "電信": {"symbol": "2412", "name": "中華電"},
    "食品": {"symbol": "1216", "name": "統一"},
}


async def analyze_lead_lag(
    symbol: str,
    benchmark: str = "TAIEX",
    days: int = 365,
    max_lag: int = 20,
) -> dict:
    """Analyze lead/lag relationship between stock and benchmark.

    Args:
        symbol: Target stock symbol (e.g., "2454")
        benchmark: "TAIEX" for market index, or a stock symbol (e.g., "2330")
        days: Number of calendar days to analyze
        max_lag: Maximum lag days to compute cross-correlation

    Returns:
        - correlation at each lag
        - optimal lag (positive = stock leads, negative = stock lags)
        - rolling lead/lag over time
        - interpretation
    """
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days + 30)  # buffer for lag computation

    # Fetch target stock
    crawler = StockPriceCrawler()
    stock_df = await crawler.get_price(symbol, str(start), str(end), "1d")

    if stock_df.empty or len(stock_df) < 60:
        return {"error": f"資料不足：{symbol} 無法取得足夠歷史數據"}

    # Fetch benchmark
    if benchmark == "TAIEX":
        # Use 0050 ETF as TAIEX proxy (correlation > 0.98)
        bench_df = await crawler.get_price("0050", str(start), str(end), "1d")
        bench_name = "加權指數(0050)"
    else:
        bench_df = await crawler.get_price(benchmark, str(start), str(end), "1d")
        leader_info = next(
            (v for v in SECTOR_LEADERS.values() if v["symbol"] == benchmark),
            None,
        )
        bench_name = leader_info["name"] if leader_info else benchmark

    if bench_df is None or bench_df.empty or len(bench_df) < 60:
        return {"error": f"基準資料不足：{bench_name}"}

    # Align dates
    stock_df["date"] = pd.to_datetime(stock_df["date"])
    bench_df["date"] = pd.to_datetime(bench_df["date"])

    stock_df = stock_df.set_index("date").sort_index()
    bench_df = bench_df.set_index("date").sort_index()

    # Compute daily returns
    stock_ret = stock_df["close"].pct_change().dropna()
    bench_ret = bench_df["close"].pct_change().dropna()

    # Align on common dates
    common_idx = stock_ret.index.intersection(bench_ret.index)
    if len(common_idx) < 40:
        return {"error": "重疊交易日不足，無法計算相關性"}

    stock_ret = stock_ret.loc[common_idx]
    bench_ret = bench_ret.loc[common_idx]

    # Cross-correlation at different lags(共用 correlation 模組,lag>0 = 股票領先)
    correlations = []
    for lag in range(-max_lag, max_lag + 1):
        corr = cross_corr_at_lag(stock_ret.values, bench_ret.values, lag)
        correlations.append({
            "lag": lag,
            "correlation": round(corr, 4),
        })

    # Find optimal lag
    best = max(correlations, key=lambda x: abs(x["correlation"]))
    optimal_lag = best["lag"]
    peak_corr = best["correlation"]

    # Concurrent correlation (lag=0)
    concurrent_corr = next(c["correlation"] for c in correlations if c["lag"] == 0)

    # Rolling lead-lag (60-day windows)
    rolling_results = _compute_rolling_lead_lag(
        stock_ret, bench_ret, window=60, max_lag=max_lag
    )

    # Build interpretation
    interpretation = _interpret(
        symbol, bench_name, optimal_lag, peak_corr, concurrent_corr, rolling_results
    )

    # Beta calculation
    beta = _compute_beta(stock_ret, bench_ret)

    return {
        "symbol": symbol,
        "benchmark": benchmark,
        "benchmark_name": bench_name,
        "trading_days": int(len(common_idx)),
        "correlations": correlations,
        "optimal_lag": optimal_lag,
        "peak_correlation": peak_corr,
        "concurrent_correlation": concurrent_corr,
        "beta": beta,
        "rolling_lead_lag": rolling_results,
        "interpretation": interpretation,
        "sector_leaders": [
            {"sector": k, "symbol": v["symbol"], "name": v["name"]}
            for k, v in SECTOR_LEADERS.items()
        ],
    }


def _fetch_taiex(start: str, end: str) -> Optional[pd.DataFrame]:
    """Fetch TAIEX index data. Tries FinMind first, then yfinance as fallback."""
    # Method 1: FinMind 0050 ETF as TAIEX proxy
    try:
        import httpx, os
        token = os.getenv("FINMIND_TOKEN", "")
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": "0050",
            "start_date": start,
            "end_date": end,
            "token": token,
        }
        resp = httpx.get(url, params=params, timeout=30)
        data = resp.json()
        if data.get("status") == 200 and data.get("data") and len(data["data"]) > 0:
            df = pd.DataFrame(data["data"])
            # FinMind columns: date, stock_id, Trading_Volume, Trading_money, open, max, min, close, spread, Trading_turnover
            df = df.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume"})
            df["date"] = pd.to_datetime(df["date"])
            if "close" in df.columns and "date" in df.columns:
                return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        import logging
        logging.warning(f"FinMind TAIEX fetch failed: {e}")

    # Method 2: yfinance ^TWII
    try:
        df = yf.download("^TWII", start=start, end=end, progress=False)
        if df.empty:
            return None
        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None


def _compute_beta(stock_ret: pd.Series, bench_ret: pd.Series) -> dict:
    """Compute beta (sensitivity to benchmark)."""
    cov = np.cov(stock_ret.values, bench_ret.values)
    beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else 1.0
    r_squared = safe_corr(stock_ret.values, bench_ret.values) ** 2
    return {
        "value": round(beta, 3),
        "r_squared": round(r_squared, 3),
        "interpretation": (
            "高度敏感（波動大於大盤）" if beta > 1.3
            else "中度敏感" if beta > 0.7
            else "低敏感（防禦型）"
        ),
    }


def _compute_rolling_lead_lag(
    stock_ret: pd.Series,
    bench_ret: pd.Series,
    window: int = 60,
    max_lag: int = 15,
) -> list:
    """Compute rolling optimal lag over time with sliding windows."""
    results = []
    dates = stock_ret.index

    for i in range(window, len(dates), 20):  # Step by 20 days
        s_window = stock_ret.iloc[i - window:i]
        b_window = bench_ret.iloc[i - window:i]

        best_lag = 0
        best_corr = 0.0

        for lag in range(-max_lag, max_lag + 1):
            corr = cross_corr_at_lag(
                s_window.values, b_window.values, lag, min_samples=15
            )
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag

        results.append({
            "date": str(dates[i - 1].date()),
            "lag": best_lag,
            "correlation": round(best_corr, 3),
        })

    return results


def _interpret(
    symbol: str,
    bench_name: str,
    optimal_lag: int,
    peak_corr: float,
    concurrent_corr: float,
    rolling: list,
) -> dict:
    """Generate human-readable interpretation."""
    # Direction
    if optimal_lag > 0:
        direction = "領先"
        direction_detail = f"{symbol} 的漲跌通常領先{bench_name}約 {optimal_lag} 個交易日"
    elif optimal_lag < 0:
        direction = "落後"
        direction_detail = f"{symbol} 的漲跌通常落後{bench_name}約 {abs(optimal_lag)} 個交易日"
    else:
        direction = "同步"
        direction_detail = f"{symbol} 與{bench_name}幾乎同步反應"

    # Correlation strength
    abs_corr = abs(peak_corr)
    if abs_corr >= 0.7:
        corr_desc = "高度相關"
    elif abs_corr >= 0.4:
        corr_desc = "中度相關"
    elif abs_corr >= 0.2:
        corr_desc = "低度相關"
    else:
        corr_desc = "幾乎無關"

    # Consistency check from rolling
    if rolling:
        lead_count = sum(1 for r in rolling if r["lag"] > 0)
        lag_count = sum(1 for r in rolling if r["lag"] < 0)
        sync_count = sum(1 for r in rolling if r["lag"] == 0)
        total = len(rolling)
        consistency = max(lead_count, lag_count, sync_count) / total * 100 if total > 0 else 0
    else:
        consistency = 0

    # Trading suggestion
    if direction == "領先" and abs_corr >= 0.4:
        suggestion = f"此股可作為{bench_name}的先行指標。當{symbol}開始明顯上漲/下跌，可預期{bench_name}將在約{optimal_lag}日後跟進。"
    elif direction == "落後" and abs_corr >= 0.4:
        suggestion = f"可觀察{bench_name}走勢來預判{symbol}。當{bench_name}出現趨勢變化，{symbol}通常在{abs(optimal_lag)}日後跟進反應。"
    elif direction == "同步":
        suggestion = f"{symbol}與{bench_name}高度連動，適合用大盤走勢直接判斷進出場時機。"
    else:
        suggestion = f"{symbol}與{bench_name}相關性低，股價走勢較獨立，建議以個股基本面或技術面為主要判斷。"

    return {
        "direction": direction,
        "direction_detail": direction_detail,
        "correlation_strength": corr_desc,
        "peak_correlation": peak_corr,
        "concurrent_correlation": concurrent_corr,
        "optimal_lag_days": optimal_lag,
        "consistency_pct": round(consistency, 1),
        "suggestion": suggestion,
    }
