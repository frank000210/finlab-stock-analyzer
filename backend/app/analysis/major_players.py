"""主力動向分析 (Market Maker / Major Player Flow Analysis).

Detects institutional accumulation (拉抬) or distribution (出貨) patterns
by analyzing:
- Institutional net buy/sell trends (外資, 投信, 自營商)
- Margin trading changes (融資融券)
- Volume-price divergence (量價背離)
- Broker concentration (券商分點集中度)
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from ..crawler import StockPriceCrawler, FinMindClient


async def analyze_major_players(symbol: str, days: int = 90) -> dict:
    """Comprehensive major-player flow analysis.

    Returns:
        - verdict: 拉抬/出貨/中性/不明
        - confidence: 0-100
        - signals: list of detected signals
        - institutional_flow: daily net buy/sell by category
        - margin_analysis: margin balance trends
        - volume_price: volume-price relationship indicators
    """
    end = date.today()
    start = end - timedelta(days=days + 10)

    client = FinMindClient()
    crawler = StockPriceCrawler()

    # Fetch all data in parallel-ish
    price_df = await crawler.get_price(symbol, str(start), str(end), "1d")
    inst_df = await client.get_institutional_investors(symbol, str(start), str(end))
    margin_df = await client.get_margin_trading(symbol, str(start), str(end))

    if price_df.empty or len(price_df) < 20:
        return {"error": "價格資料不足，無法分析主力動向"}

    price_df["date"] = pd.to_datetime(price_df["date"])
    price_df = price_df.sort_values("date").reset_index(drop=True)

    signals = []
    scores = []  # Each signal contributes a score (-100 to +100, positive = accumulation)

    # --- 1. Institutional Flow Analysis ---
    inst_result = _analyze_institutional(inst_df, signals, scores)

    # --- 2. Margin Trading Analysis ---
    margin_result = _analyze_margin(margin_df, signals, scores)

    # --- 3. Volume-Price Relationship ---
    vp_result = _analyze_volume_price(price_df, signals, scores)

    # --- 4. Price Pattern (large buy signals) ---
    pattern_result = _analyze_price_patterns(price_df, signals, scores)

    # --- Verdict ---
    if scores:
        avg_score = sum(scores) / len(scores)
    else:
        avg_score = 0

    if avg_score > 30:
        verdict = "拉抬"
        verdict_desc = "主力積極買進，股價可能持續上漲"
    elif avg_score > 10:
        verdict = "偏多"
        verdict_desc = "主力偏向買進，但力道不強"
    elif avg_score < -30:
        verdict = "出貨"
        verdict_desc = "主力持續賣出，股價可能承壓"
    elif avg_score < -10:
        verdict = "偏空"
        verdict_desc = "主力偏向賣出，需注意風險"
    else:
        verdict = "中性"
        verdict_desc = "主力方向不明確，觀望為宜"

    confidence = min(100, int(abs(avg_score) * 1.5))

    return {
        "symbol": symbol,
        "analysis_days": days,
        "verdict": verdict,
        "verdict_description": verdict_desc,
        "confidence": confidence,
        "score": round(avg_score, 1),
        "signals": signals,
        "institutional_flow": inst_result,
        "margin_analysis": margin_result,
        "volume_price": vp_result,
        "price_patterns": pattern_result,
    }


def _analyze_institutional(inst_df: pd.DataFrame, signals: list, scores: list) -> dict:
    """Analyze institutional investor buy/sell patterns."""
    if inst_df.empty or "name" not in inst_df.columns:
        return {"foreign": [], "trust": [], "dealer": [], "summary": {}}

    inst_df["date"] = pd.to_datetime(inst_df["date"])

    # Separate by investor type
    foreign_data = []
    trust_data = []
    dealer_data = []

    for dt, group in inst_df.groupby("date"):
        f_net = 0
        t_net = 0
        d_net = 0
        for _, row in group.iterrows():
            name = str(row.get("name", ""))
            buy = float(row.get("buy", 0))
            sell = float(row.get("sell", 0))
            net = buy - sell
            if "外資" in name or "Foreign" in name:
                f_net += net
            elif "投信" in name or "Investment" in name:
                t_net += net
            elif "自營" in name or "Dealer" in name:
                d_net += net

        foreign_data.append({"date": str(dt.date()) if hasattr(dt, "date") else str(dt), "net": f_net})
        trust_data.append({"date": str(dt.date()) if hasattr(dt, "date") else str(dt), "net": t_net})
        dealer_data.append({"date": str(dt.date()) if hasattr(dt, "date") else str(dt), "net": d_net})

    # Analyze trends (last 20 days)
    recent_f = [d["net"] for d in foreign_data[-20:]]
    recent_t = [d["net"] for d in trust_data[-20:]]
    recent_d = [d["net"] for d in dealer_data[-20:]]

    # Foreign investor streak
    f_streak = 0
    for v in reversed(recent_f):
        if v > 0:
            f_streak += 1
        elif v < 0:
            f_streak -= 1
            break
        else:
            break

    # Total net buy last 5/10/20 days
    f_5d = sum(recent_f[-5:]) if len(recent_f) >= 5 else 0
    f_10d = sum(recent_f[-10:]) if len(recent_f) >= 10 else 0
    f_20d = sum(recent_f[-20:]) if len(recent_f) >= 20 else sum(recent_f)

    t_5d = sum(recent_t[-5:]) if len(recent_t) >= 5 else 0
    t_10d = sum(recent_t[-10:]) if len(recent_t) >= 10 else 0

    # Signals
    if f_streak >= 5:
        signals.append({
            "type": "foreign_buy_streak",
            "label": f"外資連續買超 {f_streak} 日",
            "direction": "bullish",
            "weight": "high",
        })
        scores.append(40)
    elif f_streak <= -5:
        signals.append({
            "type": "foreign_sell_streak",
            "label": f"外資連續賣超 {abs(f_streak)} 日",
            "direction": "bearish",
            "weight": "high",
        })
        scores.append(-40)

    if t_5d > 0 and t_10d > 0:
        signals.append({
            "type": "trust_accumulating",
            "label": "投信持續加碼",
            "direction": "bullish",
            "weight": "medium",
        })
        scores.append(30)
    elif t_5d < 0 and t_10d < 0:
        signals.append({
            "type": "trust_selling",
            "label": "投信持續減碼",
            "direction": "bearish",
            "weight": "medium",
        })
        scores.append(-30)

    # Three-institutional sync buy
    if f_5d > 0 and t_5d > 0 and sum(recent_d[-5:]) > 0:
        signals.append({
            "type": "three_inst_buy",
            "label": "三大法人同步買超",
            "direction": "bullish",
            "weight": "high",
        })
        scores.append(50)
    elif f_5d < 0 and t_5d < 0 and sum(recent_d[-5:]) < 0:
        signals.append({
            "type": "three_inst_sell",
            "label": "三大法人同步賣超",
            "direction": "bearish",
            "weight": "high",
        })
        scores.append(-50)

    summary = {
        "foreign_5d": round(f_5d),
        "foreign_10d": round(f_10d),
        "foreign_20d": round(f_20d),
        "trust_5d": round(t_5d),
        "trust_10d": round(t_10d),
        "foreign_streak": f_streak,
    }

    return {
        "foreign": foreign_data[-30:],
        "trust": trust_data[-30:],
        "dealer": dealer_data[-30:],
        "summary": summary,
    }


def _analyze_margin(margin_df: pd.DataFrame, signals: list, scores: list) -> dict:
    """Analyze margin trading for accumulation/distribution signals."""
    if margin_df.empty:
        return {"data": [], "summary": {}}

    margin_df["date"] = pd.to_datetime(margin_df["date"])
    margin_df = margin_df.sort_values("date")

    # Extract balance columns
    margin_col = None
    short_col = None
    for col in margin_df.columns:
        if "MarginPurchase" in col and "Balance" in col:
            margin_col = col
        if "ShortSale" in col and "Balance" in col:
            short_col = col

    data = []
    for _, row in margin_df.iterrows():
        data.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "margin_balance": int(row.get(margin_col, 0)) if margin_col else 0,
            "short_balance": int(row.get(short_col, 0)) if short_col else 0,
        })

    if len(data) < 10:
        return {"data": data, "summary": {}}

    # Trend: compare last 5 days vs previous 5 days
    recent_margin = [d["margin_balance"] for d in data[-5:]]
    prev_margin = [d["margin_balance"] for d in data[-10:-5]]
    recent_short = [d["short_balance"] for d in data[-5:]]
    prev_short = [d["short_balance"] for d in data[-10:-5]]

    margin_change = (np.mean(recent_margin) - np.mean(prev_margin)) if prev_margin else 0
    short_change = (np.mean(recent_short) - np.mean(prev_short)) if prev_short else 0

    # Margin increasing + price up = retail chasing (散戶追高)
    # Margin decreasing + price down = forced selling (融資追繳)
    # Short increasing = bearish bets
    if margin_change > 0 and len(data) > 20:
        margin_20d_start = data[-20]["margin_balance"] if data[-20]["margin_balance"] > 0 else 1
        margin_pct_change = (data[-1]["margin_balance"] - margin_20d_start) / margin_20d_start * 100
        if margin_pct_change > 10:
            signals.append({
                "type": "margin_surge",
                "label": f"融資餘額大增 {margin_pct_change:.1f}%（散戶追買）",
                "direction": "caution",
                "weight": "medium",
            })
            scores.append(-15)  # Retail chasing is often a top signal

    if short_change > 0 and len(recent_short) > 0 and np.mean(recent_short) > 0:
        signals.append({
            "type": "short_increasing",
            "label": "融券餘額增加（空方加碼）",
            "direction": "bearish",
            "weight": "low",
        })
        scores.append(-10)
    elif short_change < 0 and abs(short_change) > np.mean(prev_short) * 0.1 if prev_short and np.mean(prev_short) > 0 else False:
        signals.append({
            "type": "short_covering",
            "label": "融券回補（空方投降）",
            "direction": "bullish",
            "weight": "medium",
        })
        scores.append(20)

    summary = {
        "margin_balance_latest": data[-1]["margin_balance"] if data else 0,
        "short_balance_latest": data[-1]["short_balance"] if data else 0,
        "margin_change_5d": round(margin_change),
        "short_change_5d": round(short_change),
    }

    return {"data": data[-30:], "summary": summary}


def _analyze_volume_price(price_df: pd.DataFrame, signals: list, scores: list) -> dict:
    """Analyze volume-price relationship for accumulation/distribution."""
    if len(price_df) < 20:
        return {"indicators": []}

    # Compute indicators
    price_df = price_df.copy()
    price_df["return"] = price_df["close"].pct_change()
    price_df["vol_ma20"] = price_df["volume"].rolling(20).mean()
    price_df["vol_ratio"] = price_df["volume"] / price_df["vol_ma20"]

    # OBV (On Balance Volume)
    obv = [0]
    for i in range(1, len(price_df)):
        if price_df.iloc[i]["close"] > price_df.iloc[i - 1]["close"]:
            obv.append(obv[-1] + price_df.iloc[i]["volume"])
        elif price_df.iloc[i]["close"] < price_df.iloc[i - 1]["close"]:
            obv.append(obv[-1] - price_df.iloc[i]["volume"])
        else:
            obv.append(obv[-1])
    price_df["obv"] = obv

    # AD Line (Accumulation/Distribution)
    ad = []
    for _, row in price_df.iterrows():
        high_low = row["high"] - row["low"]
        if high_low == 0:
            ad.append(0)
        else:
            clv = ((row["close"] - row["low"]) - (row["high"] - row["close"])) / high_low
            ad.append(clv * row["volume"])
    price_df["ad"] = np.cumsum(ad)

    # Recent analysis (last 10 days)
    recent = price_df.tail(10)
    price_up = recent["close"].iloc[-1] > recent["close"].iloc[0]
    obv_up = recent["obv"].iloc[-1] > recent["obv"].iloc[0]
    ad_up = recent["ad"].iloc[-1] > recent["ad"].iloc[0]
    avg_vol_ratio = recent["vol_ratio"].mean()

    # Volume-price divergence
    if price_up and not obv_up:
        signals.append({
            "type": "vol_price_diverge_bearish",
            "label": "量價背離（股價漲但量能萎縮）",
            "direction": "bearish",
            "weight": "medium",
        })
        scores.append(-25)
    elif not price_up and obv_up:
        signals.append({
            "type": "vol_price_diverge_bullish",
            "label": "量價背離（股價跌但有大量承接）",
            "direction": "bullish",
            "weight": "medium",
        })
        scores.append(25)

    # High volume breakout
    if avg_vol_ratio > 2.0 and price_up:
        signals.append({
            "type": "volume_breakout",
            "label": f"放量上漲（量能為均量的 {avg_vol_ratio:.1f} 倍）",
            "direction": "bullish",
            "weight": "high",
        })
        scores.append(35)

    # AD Line trend
    if ad_up and price_up:
        signals.append({
            "type": "ad_confirm",
            "label": "A/D 線確認上漲趨勢（籌碼持續流入）",
            "direction": "bullish",
            "weight": "low",
        })
        scores.append(15)

    # Return daily indicators for charting
    indicators = []
    for _, row in price_df.tail(30).iterrows():
        indicators.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]),
            "vol_ratio": round(float(row["vol_ratio"]), 2) if pd.notna(row["vol_ratio"]) else 1.0,
            "obv": int(row["obv"]),
        })

    return {"indicators": indicators}


def _analyze_price_patterns(price_df: pd.DataFrame, signals: list, scores: list) -> dict:
    """Detect price patterns indicating major player activity."""
    if len(price_df) < 20:
        return {}

    recent_20 = price_df.tail(20).copy()

    # 1. Narrow range accumulation (窄幅盤整 + volume shrink)
    price_range = (recent_20["high"].max() - recent_20["low"].min()) / recent_20["close"].mean() * 100
    vol_trend = recent_20["volume"].iloc[-5:].mean() / recent_20["volume"].iloc[:5].mean()

    if price_range < 5 and vol_trend < 0.7:
        signals.append({
            "type": "narrow_range_low_vol",
            "label": f"窄幅盤整伴隨量縮（振幅 {price_range:.1f}%），主力可能在悄悄吸籌",
            "direction": "bullish",
            "weight": "medium",
        })
        scores.append(20)

    # 2. Large body candles with volume (大量長紅/長黑)
    last_5 = price_df.tail(5)
    for _, row in last_5.iterrows():
        body_pct = abs(row["close"] - row["open"]) / row["open"] * 100
        vol_ratio = row["volume"] / price_df["volume"].rolling(20).mean().iloc[-1] if price_df["volume"].rolling(20).mean().iloc[-1] > 0 else 1

        if body_pct > 4 and vol_ratio > 2:
            if row["close"] > row["open"]:
                signals.append({
                    "type": "large_bull_candle",
                    "label": f"大量長紅K（漲幅{body_pct:.1f}%，量為均量{vol_ratio:.1f}倍）",
                    "direction": "bullish",
                    "weight": "high",
                })
                scores.append(30)
            else:
                signals.append({
                    "type": "large_bear_candle",
                    "label": f"大量長黑K（跌幅{body_pct:.1f}%，量為均量{vol_ratio:.1f}倍）",
                    "direction": "bearish",
                    "weight": "high",
                })
                scores.append(-30)
            break  # Only report one

    # 3. Upper/lower shadow analysis (長上影 = 出貨, 長下影 = 吸籌)
    last_candle = price_df.iloc[-1]
    body = abs(last_candle["close"] - last_candle["open"])
    upper_shadow = last_candle["high"] - max(last_candle["close"], last_candle["open"])
    lower_shadow = min(last_candle["close"], last_candle["open"]) - last_candle["low"]
    total_range = last_candle["high"] - last_candle["low"]

    if total_range > 0:
        if upper_shadow / total_range > 0.6 and body / total_range < 0.2:
            signals.append({
                "type": "upper_shadow",
                "label": "長上影線（上方賣壓沉重，疑似主力出貨）",
                "direction": "bearish",
                "weight": "medium",
            })
            scores.append(-20)
        elif lower_shadow / total_range > 0.6 and body / total_range < 0.2:
            signals.append({
                "type": "lower_shadow",
                "label": "長下影線（下方承接強勁，疑似主力護盤）",
                "direction": "bullish",
                "weight": "medium",
            })
            scores.append(20)

    return {
        "price_range_pct": round(price_range, 2),
        "vol_trend_ratio": round(vol_trend, 2),
    }
