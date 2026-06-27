"""Lead-Lag analysis: compare stock movements against market/sector leaders.

Uses cross-correlation of daily returns to determine if a stock leads or
lags the benchmark (TAIEX index or a sector leader), and by how many days.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional
from ..crawler import StockPriceCrawler, FinMindClient


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
        bench_df = _fetch_taiex(str(start), str(end))
        bench_name = "加權指數"
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

    # Cross-correlation at different lags
    correlations = []
    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            # Stock leads: shift stock forward (compare today's stock with future benchmark)
            s = stock_ret.iloc[:-lag].values
            b = bench_ret.iloc[lag:].values
        elif lag < 0:
            # Stock lags: shift benchmark forward
            s = stock_ret.iloc[-lag:].values
            b = bench_ret.iloc[:lag].values
        else:
            s = stock_ret.values
            b = bench_ret.values

        if len(s) < 20:
            correlations.append({"lag": lag, "correlation": 0})
            continue

        corr = float(np.corrcoef(s, b)[0, 1])
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
    """Fetch TAIEX (^TWII) from Yahoo Finance."""
    try:
        df = yf.download("^TWII", start=start, end=end, progress=False)
        if df.empty:
            return None
        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None


def _compute_beta(stock_ret: pd.Series, bench_ret: pd.Series) -> dict:
    """Compute beta (sensitivity to benchmark)."""
    cov = np.cov(stock_ret.values, bench_ret.values)
    beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else 1.0
    r_squared = float(np.corrcoef(stock_ret.values, bench_ret.values)[0, 1] ** 2)
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
        best_corr = 0

        for lag in range(-max_lag, max_lag + 1):
            if lag > 0:
                s = s_window.iloc[:-lag].values if lag < len(s_window) else []
                b = b_window.iloc[lag:].values if lag < len(b_window) else []
            elif lag < 0:
                s = s_window.iloc[-lag:].values if -lag < len(s_window) else []
                b = b_window.iloc[:lag].values if lag != 0 else b_window.values
            else:
                s = s_window.values
                b = b_window.values

            if len(s) < 15 or len(b) < 15 or len(s) != len(b):
                continue

            corr = float(np.corrcoef(s, b)[0, 1])
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
