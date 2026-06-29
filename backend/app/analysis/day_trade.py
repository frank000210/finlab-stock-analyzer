"""短線投機籌碼分析：當沖 / 隔日沖大戶估算.

利用 FinMind 免費 TaiwanStockDayTrading（當日沖銷）資料，估算：
- 當沖週轉比率：當沖成交量 / 總成交量，反映短線投機（當沖/隔日沖）熱度
- 當沖資金淨流向：當沖買進金額 − 賣出金額，推估當沖客留倉方向
- 隔日沖風險：當沖比飆高常伴隨隔日沖大戶拉抬出貨，籌碼浮動、易暴漲暴跌

當沖比由總成交量（複用法人量價資料）換算，僅需一次 DayTrading 抓取。
"""

from __future__ import annotations

from datetime import date, timedelta

from ..crawler import FinMindClient


async def analyze_day_trade(symbol: str, major: dict | None = None, days: int = 40) -> dict | None:
    """估算當沖 / 隔日沖短線投機籌碼。"""
    end = date.today()
    start = end - timedelta(days=days + 10)

    client = FinMindClient()
    try:
        df = await client._fetch(
            "TaiwanStockDayTrading",
            {"data_id": symbol, "start_date": str(start), "end_date": str(end)},
        )
    except Exception as e:
        return {"error": f"當沖資料抓取失敗：{e}"}

    if df is None or df.empty:
        return None

    # 總成交量（股）對照表：優先複用法人量價資料，否則無法計算比率
    vol_map = {}
    if major:
        for d in (major.get("volume_price") or {}).get("indicators", []):
            vol_map[d["date"]] = d.get("volume", 0) or 0

    rows = []
    for _, r in df.iterrows():
        dt = str(r.get("date", ""))[:10]
        try:
            dt_vol = float(r.get("Volume", 0) or 0)
            buy_amt = float(r.get("BuyAmount", 0) or 0)
            sell_amt = float(r.get("SellAmount", 0) or 0)
        except (TypeError, ValueError):
            continue
        total_vol = vol_map.get(dt, 0)
        ratio = round(min(100.0, dt_vol / total_vol * 100), 1) if total_vol > 0 else None
        rows.append({
            "date": dt,
            "dt_volume": int(dt_vol),
            "ratio": ratio,
            "net_amount": int(buy_amt - sell_amt),
        })

    if not rows:
        return None

    rows.sort(key=lambda x: x["date"])
    ratios = [x["ratio"] for x in rows if x["ratio"] is not None]
    recent5 = [x["ratio"] for x in rows[-5:] if x["ratio"] is not None]
    prev5 = [x["ratio"] for x in rows[-10:-5] if x["ratio"] is not None]

    avg_ratio = round(sum(ratios) / len(ratios), 1) if ratios else None
    ratio_5d = round(sum(recent5) / len(recent5), 1) if recent5 else None
    ratio_prev5 = round(sum(prev5) / len(prev5), 1) if prev5 else None
    ratio_latest = rows[-1]["ratio"]

    net_5d = sum(x["net_amount"] for x in rows[-5:])

    # 趨勢
    if ratio_5d is not None and ratio_prev5 is not None:
        trend_delta = round(ratio_5d - ratio_prev5, 1)
    else:
        trend_delta = None

    # 判讀（以近 5 日平均當沖比為主）
    base = ratio_5d if ratio_5d is not None else avg_ratio
    if base is None:
        verdict = "資料不足"
        tone = "flat"
        desc = "無足夠總成交量資料換算當沖比率。"
    elif base >= 35:
        verdict = "投機極熱"
        tone = "down"
        desc = (f"近 5 日當沖比高達 {base}%，短線當沖/隔日沖大戶高度活躍，"
                "籌碼浮動極大，慎防隔日沖拉高出貨後的回檔。")
    elif base >= 20:
        verdict = "投機偏熱"
        tone = "down"
        desc = (f"近 5 日當沖比約 {base}%，短線投機籌碼偏多，"
                "股價易受當沖客進出放大波動。")
    elif base >= 10:
        verdict = "投機中性"
        tone = "flat"
        desc = f"近 5 日當沖比約 {base}%，短線投機籌碼處於正常區間。"
    else:
        verdict = "籌碼穩定"
        tone = "up"
        desc = f"近 5 日當沖比僅約 {base}%，當沖投機比重低，籌碼相對穩定。"

    if trend_delta is not None and abs(trend_delta) >= 3:
        desc += f"（當沖比較前波{'上升' if trend_delta > 0 else '下降'} {abs(trend_delta)} 個百分點）"

    if net_5d > 0:
        net_label = f"近 5 日當沖客買進金額 > 賣出 {net_5d/1e8:.2f} 億，當沖偏積極留倉。"
    elif net_5d < 0:
        net_label = f"近 5 日當沖客賣出金額 > 買進 {abs(net_5d)/1e8:.2f} 億，當沖偏調節獲利。"
    else:
        net_label = "近 5 日當沖買賣金額相當。"

    return {
        "verdict": verdict,
        "tone": tone,
        "description": desc,
        "net_label": net_label,
        "avg_ratio": avg_ratio,
        "ratio_5d": ratio_5d,
        "ratio_latest": ratio_latest,
        "trend_delta": trend_delta,
        "net_5d": int(net_5d),
        "daily": rows[-20:],
    }
