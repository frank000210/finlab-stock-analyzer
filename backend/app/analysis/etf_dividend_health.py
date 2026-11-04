"""配息體檢：高殖利率「撐不撐得住」的規則式判讀（純函式，不碰網路與資料庫）。

要回答的問題：股價大跌時，殖利率（過去配息 ÷ 現價）會被分母變小撐大，但過去配的錢
不等於未來配得出來。這裡用 FinMind 日線＋除息紀錄（etf_compare 已經在算的同一份資料）
做四項檢查，並給出「保守／中性」情境殖利率：

1. 殖利率膨脹：現價殖利率 vs 用過去 12 個月平均價算的「常態殖利率」。
2. 配息穩定度：最近 4 次配息各自跟「去年同期」（沒有就跟前一次）比，有幾次縮水超過 20%。
   只看縮水、不看起伏：半年配、季節性高低、或越配越多的 ETF，用變異度會被誤判成不穩
   （2026-11 用真實資料檢查時抓到：0050、00929 因此被判偏弱）。
3. 近期趨勢：最近一次配息 vs 去年同期（沒有就比前幾次的平均）——台股配息有季節性，
   同期比才不會把「淡季本來就少」誤判成縮水。
4. 吃本金：近 3 年含息報酬 vs 純價格報酬——價格跌掉的幅度吃掉多少配息；再看填息成功率。

門檻全部寫在下面的常數，頁面上「計算方式」的說明要與這裡一致。資料只涵蓋「現金配息的
除息紀錄」，看不到配息的「來源」（股利／資本利得／收益平準金／本金），那是第二階段
（etf_distribution_sources）的事；這裡也不是預測，只是把歷史資料換個角度看。
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Optional

MIN_PAYOUTS = 4  # 至少幾次除息才判斷穩定度
RECENT_N = 8  # 穩定度與表格顯示最近幾次
MIN_AVG_PRICE_BARS = 60  # 算「過去 12 個月平均價」至少要有的交易日數
MIN_PRINCIPAL_BARS = 250  # 吃本金檢查至少要有的交易日數（約一年）
PRINCIPAL_YEARS = 3

# 各項檢查的門檻：(留意, 偏弱)。膨脹與 CV、吃本金是「越大越糟」，趨勢比值是「越小越糟」
INFLATION_LEVELS = (1.10, 1.30)  # 平均價 ÷ 現價
CUT_RATIO = 0.80  # 比去年同期（或前一次）少超過 20% 算「縮水」
CUT_LEVELS = (1, 2)  # 最近 4 次裡縮水幾次：>= 1 次留意、>= 2 次偏弱
STABILITY_WINDOW = 4
SURGE_RATIO = 1.5  # 最近一次比去年同期多超過 50%：不算警訊，但提醒對照配息來源
TREND_LEVELS = (0.90, 0.75)  # 最近一次 ÷ 去年同期（或前幾次平均）
EROSION_LEVELS = (0.30, 0.70)  # 價格跌幅 ÷ 配息貢獻
FILL_WEAK_RATE = 0.5  # 填息成功率低於這個，吃本金檢查再加重一級
YOY_TOLERANCE_DAYS = 45  # 找「去年同期」的容許誤差

# 給前端「判斷門檻」說明用：頁面上的數字一律從這裡來，不在前端另寫一份
THRESHOLDS = {
    "inflation": list(INFLATION_LEVELS),
    "cut_ratio": CUT_RATIO,
    "cut_levels": list(CUT_LEVELS),
    "stability_window": STABILITY_WINDOW,
    "trend": list(TREND_LEVELS),
    "erosion": list(EROSION_LEVELS),
    "fill_weak_rate": FILL_WEAK_RATE,
    "min_payouts": MIN_PAYOUTS,
    "recent_n": RECENT_N,
    "principal_years": PRINCIPAL_YEARS,
}

FREQ_LABELS = {12: "月配", 4: "季配", 2: "半年配", 1: "年配"}
LEVEL_RANK = {"good": 0, "warn": 1, "bad": 2}
VERDICT_LABELS = {"steady": "穩定", "watch": "留意", "weak": "偏弱", "unknown": "資料不足"}


def _d(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def infer_frequency(dividends: list[dict]) -> Optional[int]:
    """用最近幾次除息的間隔中位數推年配次數：≤45 天月配、≤120 季配、≤230 半年配，其餘年配。"""
    ds = [_d(d["date"]) for d in dividends][-7:]
    if len(ds) < 3:
        return None
    med = statistics.median((b - a).days for a, b in zip(ds, ds[1:]))
    if med <= 45:
        return 12
    if med <= 120:
        return 4
    if med <= 230:
        return 2
    return 1


def _level_up(value: float, warn: float, bad: float) -> str:
    """越大越糟的指標。"""
    return "bad" if value > bad else ("warn" if value > warn else "good")


def _level_down(value: float, warn: float, bad: float) -> str:
    """越小越糟的指標（warn > bad）。"""
    return "bad" if value < bad else ("warn" if value < warn else "good")


def _bump(level: str) -> str:
    return "bad" if level in ("warn", "bad") else "warn"


def verdict_from_levels(levels: list[str]) -> str:
    """四項檢查的等級 → 總評。有任何一項「偏弱」或三項以上「留意」＝偏弱；一～兩項留意＝留意；
    都沒事＝穩定；四項都算不出來（全是 na）就不要硬給「穩定」。"""
    ls = [lv for lv in levels if lv in LEVEL_RANK]
    if not ls:
        return "unknown"
    bad = sum(1 for lv in ls if lv == "bad")
    warn = sum(1 for lv in ls if lv == "warn")
    if bad >= 1 or warn >= 3:
        return "weak"
    return "watch" if warn >= 1 else "steady"


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def _vs_year_ago(dividends: list[dict], i: int) -> Optional[float]:
    """第 i 次配息 ÷ 去年同期那次（找最接近 365 天前、誤差在容許範圍內的）；找不到就 ÷ 前一次；都沒有回 None。"""
    cur = dividends[i]
    target = _d(cur["date"]) - timedelta(days=365)
    older = dividends[:i]
    best = min(older, key=lambda d: abs((_d(d["date"]) - target).days), default=None)
    if best is not None and abs((_d(best["date"]) - target).days) <= YOY_TOLERANCE_DAYS and best["amount"] > 0:
        return cur["amount"] / best["amount"]
    if i > 0 and dividends[i - 1]["amount"] > 0:
        return cur["amount"] / dividends[i - 1]["amount"]
    return None


def _unknown(reason: str, payouts: Optional[list[dict]] = None) -> dict:
    return {
        "enough": False,
        "reason": reason,
        "verdict": "unknown",
        "verdict_label": VERDICT_LABELS["unknown"],
        "payouts": payouts or [],
        "checks": [],
    }


def dividend_health(bars: list[dict], dividends: list[dict], fill: Optional[dict] = None,
                    adj: Optional[list[float]] = None) -> dict:
    """bars＝已做分割調整的日線（{date, close}）；dividends＝parse_dividends 的輸出
    （{date, amount}，現在的價格尺度）；adj＝與 bars 等長的含息還原價；fill＝fill_stats 的輸出。"""
    payouts = [{"date": d["date"], "amount": round(d["amount"], 4)} for d in dividends][-RECENT_N:]
    if not bars:
        return _unknown("沒有日線資料。")
    if not dividends:
        return _unknown("近 5 年沒有除息紀錄（不配息或尚未配息）。")

    last_close = float(bars[-1]["close"])
    last = _d(bars[-1]["date"])
    ttm_start = (last - timedelta(days=365)).isoformat()
    ttm = [d for d in dividends if d["date"] > ttm_start]
    if not ttm:
        return _unknown("近 12 個月沒有除息紀錄（可能已停止配息，或尚未進入下一次配息期）。", payouts)
    if len(dividends) < MIN_PAYOUTS:
        return _unknown(f"除息紀錄只有 {len(dividends)} 次，至少需要 {MIN_PAYOUTS} 次才能判斷穩定度。", payouts)
    if last_close <= 0:
        return _unknown("最新收盤價無效。", payouts)

    ttm_amount = sum(d["amount"] for d in ttm)
    closes_ttm = [float(b["close"]) for b in bars if b["date"] > ttm_start]
    avg_close = sum(closes_ttm) / len(closes_ttm) if len(closes_ttm) >= MIN_AVG_PRICE_BARS else None

    freq = infer_frequency(dividends)
    amounts = [d["amount"] for d in dividends][-RECENT_N:]
    checks: list[dict] = []

    # 1. 殖利率膨脹
    yield_now = ttm_amount / last_close
    yield_norm = (ttm_amount / avg_close) if avg_close else None
    inflation = (avg_close / last_close) if avg_close else None
    if inflation is None:
        checks.append({"key": "inflation", "label": "殖利率膨脹", "level": "na",
                       "text": "近 12 個月日線不足，無法算常態殖利率。"})
    else:
        lvl = _level_up(inflation, *INFLATION_LEVELS)
        if inflation > 1.0 + 1e-9:
            txt = (f"現價殖利率 {_pct(yield_now)}，若股價在近 12 個月平均價（{avg_close:.2f}）則為 {_pct(yield_norm)}；"
                   f"股價比平均低 {_pct(1 - last_close / avg_close, 0)}，殖利率被跌價撐高約 {inflation:.2f} 倍。")
        else:
            txt = f"現價殖利率 {_pct(yield_now)}，股價不低於近 12 個月平均價（{avg_close:.2f}），沒有跌價撐高的情形。"
        checks.append({"key": "inflation", "label": "殖利率膨脹", "level": lvl, "text": txt})

    # 2. 配息穩定度：最近 4 次各自比去年同期（沒有就比前一次），少超過 20% 算縮水
    mean_amt = statistics.fmean(amounts)
    cv = (statistics.pstdev(amounts) / mean_amt) if mean_amt > 0 else None  # 只留作參考，不參與判斷
    ratios = [r for r in (_vs_year_ago(dividends, i) for i in range(len(dividends) - STABILITY_WINDOW, len(dividends))) if r is not None]
    cuts = sum(1 for r in ratios if r < CUT_RATIO)
    worst = min(ratios) if ratios else None
    if worst is None:
        checks.append({"key": "stability", "label": "配息穩定度", "level": "na", "text": "沒有可比較的前期配息。"})
    else:
        lvl = "bad" if cuts >= CUT_LEVELS[1] else ("warn" if cuts >= CUT_LEVELS[0] else "good")
        rng = f"最近 {len(amounts)} 次配息 {min(amounts):.3f}～{max(amounts):.3f} 元，平均 {mean_amt:.3f}。"
        if cuts:
            txt = (f"最近 {len(ratios)} 次中有 {cuts} 次比去年同期（沒有同期就比前一次）少了 {_pct(1 - CUT_RATIO, 0)} 以上，"
                   f"最差只有 {_pct(worst, 0)}。{rng}")
        elif worst >= 1.0:
            txt = f"最近 {len(ratios)} 次都沒有比去年同期（沒有同期就比前一次）減少。{rng}"
        else:
            txt = (f"最近 {len(ratios)} 次都沒有比去年同期（沒有同期就比前一次）少超過 {_pct(1 - CUT_RATIO, 0)}"
                   f"（最差 {_pct(worst, 0)}）。{rng}")
        checks.append({"key": "stability", "label": "配息穩定度", "level": lvl, "text": txt})

    # 3. 近期趨勢：優先比去年同期
    last_div = dividends[-1]
    last_amt = last_div["amount"]
    yoy_target = _d(last_div["date"]) - timedelta(days=365)
    older = [d for d in dividends[:-1]]
    yoy = min(older, key=lambda d: abs((_d(d["date"]) - yoy_target).days), default=None)
    if yoy is not None and abs((_d(yoy["date"]) - yoy_target).days) <= YOY_TOLERANCE_DAYS and yoy["amount"] > 0:
        basis, ref_amt, ref_label = "yoy", yoy["amount"], f"去年同期（{yoy['date']}）"
    else:
        prev = [d["amount"] for d in older][-4:]
        basis, ref_amt, ref_label = ("prev_avg", statistics.fmean(prev), "前幾次平均") if prev else ("none", 0.0, "")
    trend_ratio = (last_amt / ref_amt) if ref_amt > 0 else None
    if trend_ratio is None:
        checks.append({"key": "trend", "label": "近期趨勢", "level": "na", "text": "沒有可比較的前期配息。"})
    else:
        lvl = _level_down(trend_ratio, *TREND_LEVELS)
        if trend_ratio >= SURGE_RATIO:
            verb = f"增加 {_pct(trend_ratio - 1, 0)}（增幅很大，建議對照配息來源，確認不是一次性的資本利得）"
        elif trend_ratio >= 0.98:
            verb = "持平或增加"
        else:
            verb = f"減少 {_pct(1 - trend_ratio, 0)}"
        checks.append({
            "key": "trend", "label": "近期趨勢", "level": lvl,
            "text": f"最近一次（{last_div['date']}）配 {last_amt:.3f} 元，相較{ref_label} {ref_amt:.3f} 元{verb}。",
        })

    # 4. 吃本金：近 3 年含息報酬 vs 純價格報酬
    principal = _principal(bars, adj, fill)
    checks.append(principal["check"])

    # 情境殖利率（以現價換算）：
    #  保守 = 近 12 個月 與 前一個 12 個月的配息總額取低者；中性 = 近 12 個月（就是現價殖利率）；
    #  最近一次年化 = 最近一次 × 年配次數，僅供對照（最近一次常是季節性高點，也可能是一次性配息）。
    prior_start = (last - timedelta(days=730)).isoformat()
    prior = [d for d in dividends if prior_start < d["date"] <= ttm_start]
    covers_prior = bool(prior) and bars[0]["date"] <= prior_start  # 前一個 12 個月 ETF 已經存在，總額才可比
    prior_amount = sum(d["amount"] for d in prior) if covers_prior else None
    scenarios = {
        "freq": freq,
        "freq_label": FREQ_LABELS.get(freq) if freq else None,
        "conservative": (min(ttm_amount, prior_amount) / last_close) if prior_amount else None,
        "neutral": ttm_amount / last_close,
        "last_annualized": (amounts[-1] * freq / last_close) if freq else None,
    }

    verdict = verdict_from_levels([c["level"] for c in checks])

    return {
        "enough": True,
        "reason": None,
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "freq": freq,
        "freq_label": FREQ_LABELS.get(freq) if freq else None,
        "last_close": round(last_close, 4),
        "avg_close_ttm": round(avg_close, 4) if avg_close else None,
        "yield_now": round(yield_now, 6),
        "yield_norm": round(yield_norm, 6) if yield_norm is not None else None,
        "inflation": round(inflation, 4) if inflation is not None else None,
        "ttm_amount": round(ttm_amount, 4),
        "payouts": payouts,
        "stability": {"n": len(amounts), "mean": round(mean_amt, 4), "min": round(min(amounts), 4),
                      "max": round(max(amounts), 4), "cv": round(cv, 4) if cv is not None else None,
                      "cuts": cuts, "compared": len(ratios), "worst_ratio": round(worst, 4) if worst is not None else None},
        "trend": {"basis": basis, "last": round(last_amt, 4), "ref": round(ref_amt, 4),
                  "ratio": round(trend_ratio, 4) if trend_ratio is not None else None},
        "principal": principal["data"],
        "scenarios": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in scenarios.items()},
        "checks": checks,
    }


def _principal(bars: list[dict], adj: Optional[list[float]], fill: Optional[dict]) -> dict:
    label = "吃本金檢查"
    na = {"key": "principal", "label": label, "level": "na", "text": "上市時間不夠長（不到約一年日線），不硬算。"}
    if not adj or len(adj) != len(bars) or len(bars) < MIN_PRINCIPAL_BARS:
        return {"check": na, "data": None}
    last = _d(bars[-1]["date"])
    start_day = (last - timedelta(days=int(365.25 * PRINCIPAL_YEARS))).isoformat()
    i0 = next((i for i, b in enumerate(bars) if b["date"] >= start_day), 0)
    if len(bars) - i0 < MIN_PRINCIPAL_BARS or bars[i0]["close"] <= 0 or adj[i0] <= 0:
        return {"check": na, "data": None}
    price_ret = bars[-1]["close"] / bars[i0]["close"] - 1
    total_ret = adj[-1] / adj[i0] - 1
    dist = total_ret - price_ret  # 配息（含再投入）貢獻的報酬
    years = (last - _d(bars[i0]["date"])).days / 365.25
    data = {"years": round(years, 2), "price_return": round(price_ret, 4), "total_return": round(total_ret, 4),
            "dist_contribution": round(dist, 4), "erosion": None}
    if dist <= 0.001:
        return {"check": {"key": "principal", "label": label, "level": "na", "text": "期間內幾乎沒有配息貢獻，無法比較。"},
                "data": data}
    erosion = max(0.0, -price_ret) / dist
    data["erosion"] = round(erosion, 4)
    lvl = _level_up(erosion, *EROSION_LEVELS)
    rate = (fill or {}).get("success_rate")
    fill_txt = ""
    if rate is not None:
        fill_txt = f"填息成功率 {_pct(rate, 0)}。"
        if rate < FILL_WEAK_RATE:
            lvl = _bump(lvl)
            fill_txt = f"填息成功率只有 {_pct(rate, 0)}，配息常常填不回來。"
    if price_ret >= 0:
        txt = (f"近 {years:.1f} 年價格 {price_ret * 100:+.1f}%、含息 {total_ret * 100:+.1f}%，"
               f"配息沒有被價格下跌抵銷。{fill_txt}")
    else:
        txt = (f"近 {years:.1f} 年價格 {price_ret * 100:+.1f}%、含息 {total_ret * 100:+.1f}%，"
               f"配息貢獻約 {dist * 100:.1f}%，價格下跌吃掉其中 {_pct(min(erosion, 9.99), 0)}。{fill_txt}")
    return {"check": {"key": "principal", "label": label, "level": lvl, "text": txt}, "data": data}


# ═════════════════════════════════════════════════════════════════════════════
# 文字輸出：盤後日報與殖利率警報共用（純函式）
# ═════════════════════════════════════════════════════════════════════════════

def _flagged_labels(health: dict) -> list[str]:
    return [c["label"] for c in health.get("checks", []) if c.get("level") in ("warn", "bad")]


def brief_lines(items: list[dict]) -> list[str]:
    """盤後日報的「配息體檢」段落。items＝[{symbol, name, health, yield_ttm}]。

    只列「留意／偏弱」的標的（穩定的不佔版面）；都沒事就一行帶過；全部資料不足就回空，
    日報不要塞沒有資訊的字。"""
    judged = [it for it in items if (it.get("health") or {}).get("enough")]
    if not judged:
        return []
    flagged = [it for it in judged if it["health"]["verdict"] in ("watch", "weak")]
    if not flagged:
        return [f"✓ 配息體檢：觀察清單內 {len(judged)} 檔有配息的 ETF 都沒有警示"]
    out = ["💰 配息體檢（觀察清單內的 ETF）："]
    # 偏弱排前面，同級再依殖利率膨脹由大到小
    flagged.sort(key=lambda it: (it["health"]["verdict"] != "weak", -(it["health"].get("inflation") or 0)))
    for it in flagged:
        h = it["health"]
        nm = f" {it['name']}" if it.get("name") else ""
        parts = [f"{it['symbol']}{nm}：{h['verdict_label']}", f"現價殖利率 {_pct(h['yield_now'])}"]
        if h.get("yield_norm") is not None and h.get("inflation") and h["inflation"] > 1.0:
            parts.append(f"常態 {_pct(h['yield_norm'])}（跌價撐高 {h['inflation']:.2f}×）")
        labels = _flagged_labels(h)
        if labels:
            parts.append("、".join(labels))
        out.append("・" + "｜".join(parts))
    return out


def yield_alert_message(symbol: str, name: str, target_pct: float, yield_now: float,
                        last_close: Optional[float], health: Optional[dict]) -> str:
    """殖利率警報的 Telegram 文字：殖利率高不等於配得起，所以一定附上配息體檢。"""
    nm = f" {name}" if name else ""
    close_txt = f"（收盤 {last_close:g}）" if last_close else ""
    msg = f"💰 殖利率警報：{symbol}{nm} 現價殖利率 {yield_now * 100:.2f}% 已達 {target_pct:g}%{close_txt}"
    if health and health.get("enough"):
        msg += f"\n配息體檢：{health['verdict_label']}"
        if health.get("yield_norm") is not None and health.get("inflation") and health["inflation"] > 1.0:
            msg += f"｜常態殖利率 {_pct(health['yield_norm'])}，跌價撐高 {health['inflation']:.2f}×"
        labels = _flagged_labels(health)
        if labels:
            msg += f"｜需留意：{'、'.join(labels)}"
        sc = health.get("scenarios") or {}
        parts = [f"{n} {_pct(sc[k])}" for n, k in (("保守", "conservative"), ("中性", "neutral"), ("最近一次年化", "last_annualized")) if sc.get(k) is not None]
        if parts:
            msg += "\n" + "／".join(parts)
    elif health and health.get("reason"):
        msg += f"\n配息體檢：資料不足（{health['reason']}）"
    msg += "\n（殖利率是過去配息 ÷ 現價，不代表未來配得出來；詳見 ETF 比較頁「配息體檢」，非投資建議）"
    return msg
