"""大盤多空三燈儀表板（V1，規格經五輪資深投顧審查凍結）。

三個燈與實證等級：
- 趨勢燈（A 級，Faber 2007 / Moskowitz-Ooi-Pedersen 2012）：0050 對年線，
  直接複用既有 /risk/market-regime 邏輯，也是唯一允許自動連動風險係數的燈。
- 外資期貨燈（B 級，TAIFEX 資訊交易者文獻）：外資台指期淨未平倉「金額」。
  關鍵設計：外資因現貨避險常態就是淨空（兩年中位數約 -1,714 億），絕對值
  沒有資訊量，必須用 252 日滾動分位數看「比自己平常空多少」。
- 融資燈（B 級，Barber-Lee-Liu-Odean 2009 散戶反指標）：全市場融資餘額。
  急減/斷頭是「過程訊號」——賣壓釋放中，需回穩才轉正面確認。

輸出為「體制（多方/空方/僵持）× 信心度」二維：訊號矛盾時明示僵持，
不硬湊成假中性。閾值來自 2024-07~2026-07 兩年分布校準（描述統計，
非本站回測績效保證——文獻實證的是指標「類別」，不是這組參數）。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# 融資燈閾值（兩年分布校準：單日 p5/p1、20 日 p90/p10）
MARGIN_D1_SHARP = -1.76      # 單日急減（p5）
MARGIN_D1_SHOCK = -4.97      # 斷頭潮（p1）
MARGIN_D20_OVERHEATED = 12.1  # 20 日槓桿過熱（p90）
MARGIN_D20_DELEVERAGING = -6.1  # 20 日去槓桿（p10）

ROLLING_WINDOW = 252  # 外資淨部位滾動分位數窗口（一年）
FOREIGN_EXTREME_SHORT_PCT = 20   # 低於滾動 p20 = 極端偏空
FOREIGN_BULLISH_SHIFT_PCT = 80   # 高於滾動 p80 = 偏多轉向
HISTORY_DAYS = 126  # 前端半年色帶


def _third_wednesday(y: int, m: int) -> date:
    d = date(y, m, 1)
    offset = (2 - d.weekday()) % 7  # 週三 weekday=2
    return d + timedelta(days=offset + 14)


def _is_settlement_week(today: date) -> bool:
    """台指期每月第三個週三結算，前後 3 天視為結算週（外資部位換倉噪音大）。"""
    settle = _third_wednesday(today.year, today.month)
    return abs((today - settle).days) <= 3


def _rolling_percentile(series: list[float], idx: int) -> float | None:
    """series[idx] 在其「之前」ROLLING_WINDOW 個值中的百分位（排除自己，
    避免自我納入；歷史不足 60 個交易日時回傳 None，不硬給沒意義的排名）。"""
    window = series[max(0, idx - ROLLING_WINDOW):idx]
    if len(window) < 60:
        return None
    below = sum(1 for v in window if v <= series[idx])
    return round(below / len(window) * 100, 1)


async def _foreign_futures_light() -> dict:
    """外資期貨燈：淨未平倉金額（億元）的滾動分位數判讀。"""
    from ..crawler.finmind_client import FinMindClient

    end = date.today()
    start = end - timedelta(days=550)  # 湊滿 252 交易日窗口 + 半年色帶
    df = await FinMindClient().get_futures_institutional("TX", start.isoformat(), end.isoformat())
    if df is None or df.empty:
        raise ValueError("查無台指期法人資料")
    fdf = df[df["institutional_investors"] == "外資"].sort_values("date")
    # 金額欄位單位千元 → 億元
    net = ((fdf["long_open_interest_balance_amount"] - fdf["short_open_interest_balance_amount"]) / 1e5)
    dates = [str(d)[:10] for d in fdf["date"]]
    values = [round(float(v), 1) for v in net]
    if not values:
        raise ValueError("外資期貨資料為空")

    pct = _rolling_percentile(values, len(values) - 1)
    chg5 = round(values[-1] - values[-6], 1) if len(values) >= 6 else None
    settlement = _is_settlement_week(end)

    if pct is None:
        status, tone = "insufficient", "flat"
    elif pct <= FOREIGN_EXTREME_SHORT_PCT:
        status, tone = "extreme_short", "bad"
    elif pct >= FOREIGN_BULLISH_SHIFT_PCT:
        status, tone = "bullish_shift", "good"
    else:
        status, tone = "neutral", "flat"

    # 雙向敘事（審查 P13：極端訊號必須兩面都講）
    if status == "extreme_short":
        narrative = (
            f"外資淨空單金額 {abs(values[-1]):,.0f} 億，比過去一年 {100 - (pct or 0):.0f}% 的時間都更空——"
            "資訊交易者明顯站在空方，屬偏空訊號；但極端空單同時是未來回補的燃料，"
            "一旦趨勢反轉，空單回補會放大漲勢。"
        )
    elif status == "bullish_shift":
        narrative = (
            f"外資淨部位升至過去一年第 {pct:.0f} 百分位——相對自身常態明顯轉多，"
            "歷史上屬偏多訊號；但需留意是否為除息/結算的暫時性調整。"
        )
    elif status == "insufficient":
        narrative = "歷史資料不足一年，暫不判讀。"
    else:
        narrative = (
            f"外資淨部位處於過去一年第 {pct:.0f} 百分位，相對自身常態無明顯偏移"
            "（外資因現貨避險常態即為淨空，絕對數字不代表看空）。"
        )
    if settlement:
        narrative += "（本週為台指期結算週，部位換倉噪音較大，判讀降權）"

    return {
        "status": status,
        "tone": tone,
        "net_amount_yi": values[-1],
        "rolling_percentile": pct,
        "chg5_yi": chg5,
        "settlement_week": settlement,
        "narrative": narrative,
        "history": [{"date": d, "value": v} for d, v in zip(dates[-HISTORY_DAYS:], values[-HISTORY_DAYS:])],
        "as_of": dates[-1],
        "evidence": "B",
        "publish_note": "期交所每交易日約 15:00 後公布，盤前看到的是前一交易日資料",
    }


async def _margin_light() -> dict:
    """融資燈：全市場融資餘額（散戶槓桿反指標）。"""
    from ..crawler.finmind_client import FinMindClient

    end = date.today()
    start = end - timedelta(days=270)
    df = await FinMindClient().get_total_margin(start.isoformat(), end.isoformat())
    if df is None or df.empty:
        raise ValueError("查無融資餘額資料")
    mdf = df[df["name"] == "MarginPurchaseMoney"].sort_values("date")
    dates = [str(d)[:10] for d in mdf["date"]]
    values = [round(float(v) / 1e8, 1) for v in mdf["TodayBalance"]]  # 元 → 億
    if len(values) < 21:
        raise ValueError("融資餘額資料不足")

    d1 = round((values[-1] / values[-2] - 1) * 100, 2)
    d20 = round((values[-1] / values[-21] - 1) * 100, 1)
    recent_d1 = [
        (values[i] / values[i - 1] - 1) * 100
        for i in range(max(1, len(values) - 5), len(values))
    ]
    had_recent_shock = any(c <= MARGIN_D1_SHARP for c in recent_d1[:-1])

    # 優先序：斷頭潮 > 急減 > 回穩確認 > 過熱 > 去槓桿 > 正常
    if d1 <= MARGIN_D1_SHOCK:
        status, tone = "shock", "bad"
        narrative = (
            f"融資餘額單日 -{abs(d1)}%（{values[-1]:,.0f} 億），達兩年分布最劇烈 1% 的斷頭潮等級——"
            "散戶槓桿正被強制清洗。這是「賣壓釋放中」的過程訊號，不是進場訊號；"
            "歷史上斷頭潮常出現在底部區附近，但需等餘額止穩才算清洗完成。"
        )
    elif d1 <= MARGIN_D1_SHARP:
        status, tone = "sharp_decline", "warn"
        narrative = f"融資餘額單日 {d1}%，屬急減（兩年分布約 5% 分位）——去槓桿壓力進行中，等止穩。"
    elif had_recent_shock and d1 >= 0:
        status, tone = "stabilizing", "good"
        narrative = (
            f"近日曾出現融資急減，今日餘額止穩（{d1:+}%）——斷頭賣壓可能已釋放大半，"
            "屬偏正面的確認訊號；但若再度轉急減則此判讀作廢。"
        )
    elif d20 >= MARGIN_D20_OVERHEATED:
        status, tone = "overheated", "warn"
        narrative = (
            f"融資餘額 20 日 +{d20}%（兩年分布約前 10%）——散戶槓桿快速堆積。"
            "實證上散戶整體是反指標，槓桿過熱處行情通常已偏晚段；但過熱可以持續一段時間，不是立即反轉訊號。"
        )
    elif d20 <= MARGIN_D20_DELEVERAGING:
        status, tone = "deleveraging", "flat"
        narrative = f"融資餘額 20 日 {d20}%——散戶持續去槓桿，籌碼負擔減輕中。"
    else:
        status, tone = "normal", "flat"
        narrative = f"融資餘額 {values[-1]:,.0f} 億，單日 {d1:+}%、20 日 {d20:+}%，散戶槓桿無異常。"

    return {
        "status": status,
        "tone": tone,
        "balance_yi": values[-1],
        "d1_pct": d1,
        "d20_pct": d20,
        "narrative": narrative,
        "history": [{"date": d, "value": v} for d, v in zip(dates[-HISTORY_DAYS:], values[-HISTORY_DAYS:])],
        "as_of": dates[-1],
        "evidence": "B",
        "publish_note": "交易所每交易日約 21:00 後公布，盤前看到的是前一交易日資料",
    }


def _combine(trend: dict, foreign: dict | None, margin: dict | None) -> dict:
    """審查 P5：輸出「體制 × 信心」，訊號矛盾時明示僵持而非假中性。"""
    trend_bull = bool(trend.get("above_ma200"))
    contradictions = []
    supports = []

    if foreign:
        if foreign["status"] == "extreme_short":
            (contradictions if trend_bull else supports).append("外資期貨極端淨空")
        elif foreign["status"] == "bullish_shift":
            (supports if trend_bull else contradictions).append("外資期貨部位轉多")
    if margin:
        if margin["status"] in ("shock", "sharp_decline"):
            # 過程訊號：多頭中出現斷頭＝矛盾（激烈換手）；空頭中屬順向確認
            (contradictions if trend_bull else supports).append("融資斷頭/急減進行中")
        elif margin["status"] == "overheated":
            (contradictions if trend_bull else supports).append("散戶槓桿過熱")
        elif margin["status"] == "stabilizing":
            (supports if trend_bull else contradictions).append("融資止穩（賣壓釋放尾聲）")

    if contradictions:
        regime, label = "stalemate", "僵持"
        confidence = "low"
        narrative = (
            f"趨勢燈{'偏多' if trend_bull else '偏空'}，但{'、'.join(contradictions)}與其矛盾——"
            "屬「僵持」狀態：" +
            ("長線結構未壞、短線籌碼激烈換手中，不是進場好時機，也還不到全面看空。"
             if trend_bull else
             "長線趨勢偏空、但籌碼出現反向訊號，空方追價風險升高。")
        )
    else:
        regime = "bull" if trend_bull else "bear"
        label = "多方" if trend_bull else "空方"
        confidence = "high" if supports else "medium"
        narrative = (
            f"趨勢燈{'偏多' if trend_bull else '偏空'}"
            + (f"，且{'、'.join(supports)}同向確認" if supports else "，籌碼燈無矛盾訊號")
            + "。體制為狀態描述，非漲跌預測。"
        )
    return {"regime": regime, "label": label, "confidence": confidence, "narrative": narrative}


async def build_market_lights() -> dict:
    """三燈儀表板本體。B 級燈抓取失敗時降級為單燈判讀並標註（審查 P8）。"""
    from ..api.risk import market_regime
    from ..db.cache import get_cache, set_cache

    cache_key = "market_lights:v1"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    trend = (await market_regime())["data"]

    foreign = None
    margin = None
    errors = {}
    try:
        foreign = await _foreign_futures_light()
    except Exception as exc:
        errors["foreign_futures"] = str(exc)[:120]
        logger.warning("foreign futures light failed: %s", exc)
    try:
        margin = await _margin_light()
    except Exception as exc:
        errors["margin"] = str(exc)[:120]
        logger.warning("margin light failed: %s", exc)

    result = {
        "combined": _combine(trend, foreign, margin),
        "lights": {
            "trend": {**trend, "evidence": "A", "tone": "good" if trend.get("above_ma200") else "bad"},
            "foreign_futures": foreign,
            "margin": margin,
        },
        "errors": errors or None,
        "calibration_note": "籌碼燈閾值為 2024-07~2026-07 兩年分布之描述統計校準；文獻實證的是指標類別，非本組參數之回測績效保證。",
    }
    try:
        await set_cache(cache_key, result, "market_lights")
    except Exception:
        pass
    return result
