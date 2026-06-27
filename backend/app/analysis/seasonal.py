"""Seasonal pattern analysis for individual stocks.

Analyzes multi-year historical data to identify recurring monthly/quarterly
patterns such as year-end window dressing (作帳行情), dividend season effects,
or earnings-driven cycles.
"""

import pandas as pd
import numpy as np
from typing import Optional
from ..crawler import StockPriceCrawler


async def analyze_seasonal_patterns(
    symbol: str, years: int = 5
) -> dict:
    """Analyze seasonal (monthly) return patterns over multiple years.

    Returns:
        - monthly_avg: Average return per month across all years
        - monthly_win_rate: Percentage of years that month was positive
        - yearly_returns: Each year's monthly returns matrix
        - patterns: Detected patterns with explanations
        - quarterly_summary: Quarterly aggregated stats
    """
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=365 * years + 60)  # Extra buffer

    crawler = StockPriceCrawler()
    df = await crawler.get_price(symbol, str(start), str(end), "1d")

    if df.empty or len(df) < 60:
        return {"error": "資料不足，無法進行季節性分析", "months": []}

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    # Calculate monthly returns: close of last trading day vs first trading day
    monthly_returns = []
    for (year, month), group in df.groupby(["year", "month"]):
        if len(group) < 5:
            continue
        first_close = group.iloc[0]["close"]
        last_close = group.iloc[-1]["close"]
        ret = (last_close - first_close) / first_close * 100
        monthly_returns.append({
            "year": int(year),
            "month": int(month),
            "return_pct": round(ret, 2),
            "open_price": round(float(first_close), 2),
            "close_price": round(float(last_close), 2),
            "high": round(float(group["high"].max()), 2),
            "low": round(float(group["low"].min()), 2),
            "avg_volume": int(group["volume"].mean()),
        })

    if not monthly_returns:
        return {"error": "資料不足", "months": []}

    mr_df = pd.DataFrame(monthly_returns)

    # Monthly average & win rate
    month_stats = []
    for m in range(1, 13):
        m_data = mr_df[mr_df["month"] == m]
        if m_data.empty:
            month_stats.append({
                "month": m,
                "avg_return": 0,
                "median_return": 0,
                "win_rate": 0,
                "max_return": 0,
                "min_return": 0,
                "std": 0,
                "sample_years": 0,
            })
            continue

        returns = m_data["return_pct"].values
        month_stats.append({
            "month": m,
            "avg_return": round(float(np.mean(returns)), 2),
            "median_return": round(float(np.median(returns)), 2),
            "win_rate": round(float(np.sum(returns > 0) / len(returns) * 100), 1),
            "max_return": round(float(np.max(returns)), 2),
            "min_return": round(float(np.min(returns)), 2),
            "std": round(float(np.std(returns)), 2),
            "sample_years": int(len(returns)),
        })

    # Quarterly summary
    quarter_map = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4, 11: 4, 12: 4}
    quarterly_stats = []
    for q in range(1, 5):
        q_months = [m for m, qval in quarter_map.items() if qval == q]
        q_data = mr_df[mr_df["month"].isin(q_months)]
        if q_data.empty:
            quarterly_stats.append({"quarter": q, "avg_return": 0, "win_rate": 0})
            continue
        # Group by year, sum monthly returns within quarter
        q_yearly = q_data.groupby("year")["return_pct"].sum()
        quarterly_stats.append({
            "quarter": q,
            "avg_return": round(float(q_yearly.mean()), 2),
            "win_rate": round(float((q_yearly > 0).sum() / len(q_yearly) * 100), 1),
        })

    # Detect patterns
    patterns = _detect_patterns(month_stats, quarterly_stats, mr_df)

    # Year-by-year matrix
    yearly_matrix = []
    for year in sorted(mr_df["year"].unique()):
        year_data = mr_df[mr_df["year"] == year]
        row = {"year": int(year), "months": {}}
        for _, r in year_data.iterrows():
            row["months"][int(r["month"])] = round(r["return_pct"], 2)
        yearly_matrix.append(row)

    return {
        "symbol": symbol,
        "years_analyzed": int(mr_df["year"].nunique()),
        "period": f"{int(mr_df['year'].min())}–{int(mr_df['year'].max())}",
        "month_stats": month_stats,
        "quarterly_stats": quarterly_stats,
        "yearly_matrix": yearly_matrix,
        "patterns": patterns,
        "raw_monthly": monthly_returns,
    }


def _detect_patterns(
    month_stats: list, quarterly_stats: list, mr_df: pd.DataFrame
) -> list:
    """Detect notable seasonal patterns and provide explanations."""
    patterns = []

    # 1. Year-end window dressing (作帳行情): Nov-Dec strong
    nov_dec = [ms for ms in month_stats if ms["month"] in (11, 12)]
    if all(ms["win_rate"] >= 60 and ms["avg_return"] > 0.5 for ms in nov_dec if ms["sample_years"] >= 3):
        avg = round(sum(ms["avg_return"] for ms in nov_dec) / 2, 2)
        wr = round(sum(ms["win_rate"] for ms in nov_dec) / 2, 1)
        patterns.append({
            "type": "year_end_rally",
            "name": "年底作帳行情",
            "months": [11, 12],
            "strength": _strength(wr),
            "description": f"11-12月平均上漲 {avg}%，勝率 {wr}%。法人年底結帳前傾向拉抬持股市值，形成「作帳行情」。",
            "suggestion": "可考慮在10月底佈局，12月中旬獲利了結。",
        })

    # 2. Mid-year rally (年中行情): Jun-Jul
    jun_jul = [ms for ms in month_stats if ms["month"] in (6, 7)]
    if all(ms["win_rate"] >= 60 and ms["avg_return"] > 0.5 for ms in jun_jul if ms["sample_years"] >= 3):
        avg = round(sum(ms["avg_return"] for ms in jun_jul) / 2, 2)
        wr = round(sum(ms["win_rate"] for ms in jun_jul) / 2, 1)
        patterns.append({
            "type": "mid_year_rally",
            "name": "年中行情",
            "months": [6, 7],
            "strength": _strength(wr),
            "description": f"6-7月平均上漲 {avg}%，勝率 {wr}%。可能與半年報預期、除權息行情或法人半年結帳有關。",
            "suggestion": "5月底可關注是否出現買進訊號。",
        })

    # 3. January effect (元月效應)
    jan = next((ms for ms in month_stats if ms["month"] == 1), None)
    if jan and jan["win_rate"] >= 65 and jan["avg_return"] > 1.0 and jan["sample_years"] >= 3:
        patterns.append({
            "type": "january_effect",
            "name": "元月效應",
            "months": [1],
            "strength": _strength(jan["win_rate"]),
            "description": f"1月平均上漲 {jan['avg_return']}%，勝率 {jan['win_rate']}%。新年度資金回流、投信作帳需求推升股價。",
            "suggestion": "前一年12月底可提前佈局。",
        })

    # 4. Sell in May (五窮六絕)
    may_jun = [ms for ms in month_stats if ms["month"] in (5, 6)]
    if all(ms["win_rate"] <= 40 and ms["avg_return"] < -0.5 for ms in may_jun if ms["sample_years"] >= 3):
        avg = round(sum(ms["avg_return"] for ms in may_jun) / 2, 2)
        patterns.append({
            "type": "sell_in_may",
            "name": "五窮六絕",
            "months": [5, 6],
            "strength": _strength(100 - sum(ms["win_rate"] for ms in may_jun) / 2),
            "description": f"5-6月平均下跌 {abs(avg)}%。符合「Sell in May」效應，外資傾向在此期間減碼。",
            "suggestion": "4月底若持有部位較重，可考慮減碼。",
        })

    # 5. Ex-dividend season (除權息行情): Jul-Aug for stocks with high yield
    jul_aug = [ms for ms in month_stats if ms["month"] in (7, 8)]
    if any(ms["avg_return"] > 1.5 and ms["win_rate"] >= 60 for ms in jul_aug if ms["sample_years"] >= 3):
        avg = round(max(ms["avg_return"] for ms in jul_aug), 2)
        patterns.append({
            "type": "dividend_season",
            "name": "除權息行情",
            "months": [7, 8],
            "strength": "中",
            "description": f"7-8月表現強勁（最高月均 +{avg}%），可能與除權息前搶權或填權行情有關。",
            "suggestion": "留意該股除權息日，提前佈局搶權或等待填權。",
        })

    # 6. Q1 strong (第一季旺季)
    q1 = next((qs for qs in quarterly_stats if qs["quarter"] == 1), None)
    if q1 and q1["avg_return"] > 3 and q1["win_rate"] >= 70:
        patterns.append({
            "type": "q1_strong",
            "name": "第一季旺季效應",
            "months": [1, 2, 3],
            "strength": _strength(q1["win_rate"]),
            "description": f"Q1 累積平均漲幅 {q1['avg_return']}%，勝率 {q1['win_rate']}%。可能與農曆年紅包行情及新年度佈局有關。",
            "suggestion": "年初為佈局時機，3月底可考慮減碼。",
        })

    # 7. Consistent weak months
    for ms in month_stats:
        if ms["sample_years"] >= 4 and ms["win_rate"] <= 25 and ms["avg_return"] < -1:
            month_name = _month_name(ms["month"])
            patterns.append({
                "type": "weak_month",
                "name": f"{month_name}固定弱勢",
                "months": [ms["month"]],
                "strength": "強",
                "description": f"{month_name}平均下跌 {abs(ms['avg_return'])}%，勝率僅 {ms['win_rate']}%（{ms['sample_years']}年數據）。建議避開此月份。",
                "suggestion": f"前一個月底可考慮先行減碼或設定停損。",
            })

    # 8. Consistent strong months
    for ms in month_stats:
        if ms["sample_years"] >= 4 and ms["win_rate"] >= 80 and ms["avg_return"] > 2:
            month_name = _month_name(ms["month"])
            patterns.append({
                "type": "strong_month",
                "name": f"{month_name}固定強勢",
                "months": [ms["month"]],
                "strength": "強",
                "description": f"{month_name}平均上漲 {ms['avg_return']}%，勝率高達 {ms['win_rate']}%（{ms['sample_years']}年數據）。歷史上幾乎每年都漲。",
                "suggestion": f"每年可固定在{_month_name(ms['month'] - 1 if ms['month'] > 1 else 12)}底佈局。",
            })

    # If no patterns detected
    if not patterns:
        patterns.append({
            "type": "no_pattern",
            "name": "無明顯季節性規律",
            "months": [],
            "strength": "–",
            "description": "該股過去數年無明顯的月份性規律，漲跌較為隨機。建議改以基本面或技術面為主要判斷依據。",
            "suggestion": "可嘗試拉長分析年份，或觀察產業淡旺季。",
        })

    return patterns


def _strength(win_rate: float) -> str:
    """Map win rate to strength label."""
    if win_rate >= 80:
        return "強"
    elif win_rate >= 65:
        return "中"
    else:
        return "弱"


MONTH_NAMES = [
    "", "一月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "十一月", "十二月",
]


def _month_name(m: int) -> str:
    return MONTH_NAMES[m]
