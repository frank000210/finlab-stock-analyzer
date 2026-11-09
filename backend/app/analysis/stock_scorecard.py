"""個股三面向評分卡：基本面、技術面、籌碼面各 10 項「通過／未通過／不適用」檢核。

設計原則（見 docs/改善紀錄 與 plans）：
- **透明**：每一項都附「實際值 vs 門檻」，不是黑盒分數；
- **一份算法**：技術指標沿用 TechnicalAnalyzer（與個股分析頁其他地方同一套數字），
  籌碼沿用 api/chip.py 的 _build_chip_analysis 快取；前端不再自己重算；
- **不適用不是 0 分**：金融保險股沒有毛利、ROE 門檻不同；資料不足的項目標「不適用」，
  面向分數＝通過數 ÷ 可判定數 × 10；
- **地雷用旗標，不用分數稀釋**：負債比、營業現金流、乖離過大等只警示、不計分；
- **現況描述，不是預測**：這些門檻沒有經過回測驗證（見 docs/待驗主張清冊.md C10–C12）。
  「現價 ≥ 主力成本」已被回測證實不顯著（C1–C3），所以不計分。

檢核項的門檻參考一張同類產品的宣傳圖，並依本專案的資料與驗證原則改良；
沒有券商分點資料（FinMind 免費等級讀不到），所以籌碼面改用法人、集保、融資、當沖、外資持股。
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Optional

import pandas as pd

from .technical import TechnicalAnalyzer

SCORECARD_VERSION = "v1"
MIN_DECIDABLE = 5  # 一個面向可判定的項數少於這個，就不給面向分數（資料不足）

PASS, FAIL, NA = "pass", "fail", "na"

# FinMind 的稅後淨利欄位名稱：一般公司 IncomeAfterTaxes，金融保險業是 IncomeAfterTax（單數）
NET_INCOME_KEYS = ("IncomeAfterTaxes", "IncomeAfterTax", "IncomeFromContinuingOperations")

# 門檻（集中放這裡；任何調整都要同步 docs/待驗主張清冊.md）
TH = {
    "yield_min": 3.0,           # 現金殖利率 %
    "roe_min": 8.0,             # 近四季 ROE %
    "rsi_lo": 50.0, "rsi_hi": 70.0,
    "vol_ratio": 1.2,
    "kd_hot": 80.0,
    "new_high_days": 60,
    "rev_high_months": 10,
    "daytrade_max": 30.0,       # 近 5 日當沖比 %
    "debt_warn": 60.0,
    "overheat_rsi": 75.0, "overheat_ma20": 0.15,
}


# ═════════════════════════════════════════════════════════════════════════════
# 小工具
# ═════════════════════════════════════════════════════════════════════════════

def _ok(x: Any) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _n(x: Any, d: int = 2) -> str:
    if not _ok(x):
        return "—"
    x = float(x)
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.{d}f}"


def _pct(x: Any, d: int = 1) -> str:
    return f"{float(x):.{d}f}%" if _ok(x) else "—"


def _item(id_: str, label: str, status: str, value: str = "", threshold: str = "", note: str = "") -> dict:
    return {"id": id_, "label": label, "status": status, "value": value, "threshold": threshold, "note": note}


def _na(id_: str, label: str, threshold: str, why: str) -> dict:
    return _item(id_, label, NA, "—", threshold, why)


def _judge(id_: str, label: str, passed: bool, value: str, threshold: str, note: str = "") -> dict:
    return _item(id_, label, PASS if passed else FAIL, value, threshold, note)


# ═════════════════════════════════════════════════════════════════════════════
# 技術面（T1–T10）
# ═════════════════════════════════════════════════════════════════════════════

_TECH_LABELS = [
    ("T1", "收盤 > 5 日均線（週線）"),
    ("T2", "收盤 > 20 日均線（月線）"),
    ("T3", "20 日均線 > 60 日均線（月線在季線上）"),
    ("T4", "均線多頭排列（5 > 10 > 20）"),
    ("T5", "MACD 的 DIF > DEA"),
    ("T6", "RSI14 在 50～70（多頭且未過熱）"),
    ("T7", "KD 近 3 日黃金交叉且 K < 80"),
    ("T8", "量增收漲（量 ≥ 20 日均量 1.2 倍且收盤上漲）"),
    ("T9", "近 3 日累計漲幅勝過加權指數"),
    ("T10", "收盤創 60 日新高"),
]


def compute_technical_frame(bars: list[dict]) -> Optional[pd.DataFrame]:
    """日線 → 帶 MA／MACD／KD／RSI／均量的 DataFrame（沿用 TechnicalAnalyzer，與個股分析頁同一套）。"""
    if not bars or len(bars) < 30:
        return None
    df = pd.DataFrame(bars)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    if len(df) < 30:
        return None
    return TechnicalAnalyzer().compute(
        df, ["ma", "macd", "kd", "rsi", "volume"], {"ma_periods": [5, 10, 20, 60, 240]}
    )


def technical_checks(bars: list[dict], taiex: Optional[list[dict]] = None, frame: Optional[pd.DataFrame] = None) -> list[dict]:
    comp = frame if frame is not None else compute_technical_frame(bars)
    if comp is None:
        return [_na(i, lb, "", "日線不足 30 根，無法判斷") for i, lb in _TECH_LABELS]

    n = len(comp)
    last = comp.iloc[-1]
    prev = comp.iloc[-2]
    close, ma5, ma10, ma20, ma60 = (last.get(c) for c in ("close", "ma5", "ma10", "ma20", "ma60"))
    out: list[dict] = []
    lab = dict(_TECH_LABELS)

    def need(id_: str, *vals: Any) -> bool:
        if all(_ok(v) for v in vals):
            return True
        out.append(_na(id_, lab[id_], "", "資料不足（上市未滿或停牌多）"))
        return False

    if need("T1", close, ma5):
        out.append(_judge("T1", lab["T1"], close > ma5, f"收盤 {_n(close)}／5MA {_n(ma5)}", "收盤 > 5MA"))
    if need("T2", close, ma20):
        out.append(_judge("T2", lab["T2"], close > ma20, f"收盤 {_n(close)}／20MA {_n(ma20)}", "收盤 > 20MA"))
    if need("T3", ma20, ma60):
        out.append(_judge("T3", lab["T3"], ma20 > ma60, f"20MA {_n(ma20)}／60MA {_n(ma60)}", "20MA > 60MA"))
    if need("T4", ma5, ma10, ma20):
        out.append(_judge("T4", lab["T4"], ma5 > ma10 > ma20, f"5MA {_n(ma5)}／10MA {_n(ma10)}／20MA {_n(ma20)}", "5MA > 10MA > 20MA"))

    dif, dea = last.get("macd_dif"), last.get("macd_dea")
    if need("T5", dif, dea):
        out.append(_judge("T5", lab["T5"], dif > dea, f"DIF {_n(dif)}／DEA {_n(dea)}", "DIF > DEA"))

    rsi = last.get("rsi14")
    if need("T6", rsi):
        out.append(_judge("T6", lab["T6"], TH["rsi_lo"] <= rsi <= TH["rsi_hi"], f"RSI14 {_n(rsi, 1)}", "50 ≤ RSI ≤ 70",
                          "高於 70 視為過熱、低於 50 偏弱" if not (TH["rsi_lo"] <= rsi <= TH["rsi_hi"]) else ""))

    k, d = comp["k"], comp["d"]
    if n >= 12 and all(_ok(x) for x in (k.iloc[-1], d.iloc[-1], k.iloc[-4], d.iloc[-4])):
        crossed = any(
            _ok(k.iloc[j - 1]) and _ok(d.iloc[j - 1]) and k.iloc[j - 1] <= d.iloc[j - 1] and k.iloc[j] > d.iloc[j]
            for j in range(n - 3, n)
        )
        out.append(_judge("T7", lab["T7"], crossed and k.iloc[-1] < TH["kd_hot"],
                          f"K {_n(k.iloc[-1], 1)}／D {_n(d.iloc[-1], 1)}", "近 3 日 K 由下穿上 D，且 K < 80"))
    else:
        out.append(_na("T7", lab["T7"], "", "資料不足"))

    vol, vol_ma20 = last.get("volume"), last.get("vol_ma20")
    if need("T8", vol, vol_ma20, close, prev.get("close")):
        if vol_ma20 > 0:
            ratio = vol / vol_ma20
            out.append(_judge("T8", lab["T8"], ratio >= TH["vol_ratio"] and close > prev["close"],
                              f"量為 20 日均量的 {ratio:.2f} 倍、{'收漲' if close > prev['close'] else '收跌或平盤'}",
                              "≥ 1.2 倍且收盤上漲"))
        else:
            out.append(_na("T8", lab["T8"], "", "20 日均量為 0（停牌或無成交）"))

    out.append(_relative_to_market(comp, taiex, lab["T9"]))

    if n >= TH["new_high_days"]:
        hi = comp["close"].tail(TH["new_high_days"]).max()
        out.append(_judge("T10", lab["T10"], close >= hi, f"收盤 {_n(close)}／近 60 日最高收盤 {_n(hi)}", "收盤 ≥ 近 60 日最高收盤"))
    else:
        out.append(_na("T10", lab["T10"], "", "日線不足 60 根"))

    order = {i: k_ for k_, (i, _) in enumerate(_TECH_LABELS)}
    return sorted(out, key=lambda it: order[it["id"]])


def _relative_to_market(comp: pd.DataFrame, taiex: Optional[list[dict]], label: str) -> dict:
    if not taiex or len(taiex) < 5 or len(comp) < 5:
        return _na("T9", label, "", "沒有加權指數資料")
    tx = {str(r["date"])[:10]: float(r["close"]) for r in taiex if _ok(r.get("close"))}
    dates = [str(x)[:10] for x in comp["date"].tail(4)]
    if not all(d in tx for d in dates):
        return _na("T9", label, "", "個股與加權指數的交易日對不上")
    s = comp["close"].tail(4).tolist()
    stock_ret = s[-1] / s[0] - 1
    mkt_ret = tx[dates[-1]] / tx[dates[0]] - 1
    return _judge("T9", label, stock_ret > mkt_ret,
                  f"個股 {stock_ret * 100:+.1f}%／大盤 {mkt_ret * 100:+.1f}%", "個股 3 日報酬 > 加權指數")


# ═════════════════════════════════════════════════════════════════════════════
# 基本面（F1–F10）
# ═════════════════════════════════════════════════════════════════════════════

_FUND_LABELS = [
    ("F1", "本益比為正，且不高於自身近 3 年中位數"),
    ("F2", "股價淨值比不高於自身近 3 年中位數"),
    ("F3", "現金殖利率 ≥ 3%"),
    ("F4", "月營收創 10 個月新高"),
    ("F5", "近 3 月平均營收年增率 > 0"),
    ("F6", "最近一季營業利益 > 0"),
    ("F7", "最近一季稅後淨利 > 0"),
    ("F8", "近四季 EPS 合計 > 前四季合計"),
    ("F9", "近四季 ROE ≥ 8%"),
    ("F10", "毛利率不低於去年同期"),
]


def is_financial_industry(industry: str) -> bool:
    s = industry or ""
    return "金融" in s or "保險" in s or "銀行" in s


def _quarters(d: dict[str, dict[str, float]]) -> list[str]:
    return sorted(d.keys())


def _prev_year(q: str) -> str:
    return f"{int(q[:4]) - 1}{q[4:]}"


def _median_valid(rows: list[dict], key: str) -> tuple[Optional[float], int]:
    vals = [float(r[key]) for r in rows if _ok(r.get(key)) and float(r[key]) > 0]
    return (statistics.median(vals), len(vals)) if vals else (None, 0)


def fundamental_checks(per_rows: list[dict], revenue: list[dict], fin_q: dict, bs_q: dict, industry: str = "") -> list[dict]:
    lab = dict(_FUND_LABELS)
    out: list[dict] = []
    financial = is_financial_industry(industry)

    # F1／F2：相對自身歷史的估值（原圖的「PE ≥ 10」是下限、越貴越容易過，不是便宜）
    last_val = per_rows[-1] if per_rows else {}
    for id_, key, name in (("F1", "PER", "本益比"), ("F2", "PBR", "股價淨值比")):
        cur = last_val.get(key)
        median, cnt = _median_valid(per_rows, key)
        if not per_rows or median is None or cnt < 100:
            out.append(_na(id_, lab[id_], "", "估值歷史不足 100 個交易日"))
        elif not _ok(cur) or float(cur) <= 0:
            out.append(_item(id_, lab[id_], FAIL, f"{name}無法計算（虧損或無資料）", f"0 < {name} ≤ 近 3 年中位數 {_n(median, 1)}"))
        else:
            out.append(_judge(id_, lab[id_], float(cur) <= median, f"{name} {_n(cur, 1)}／近 3 年中位數 {_n(median, 1)}",
                              f"{name} ≤ 中位數"))

    # F3：殖利率
    if last_val and "dividend_yield" in last_val and _ok(last_val.get("dividend_yield")):
        y = float(last_val["dividend_yield"])
        out.append(_judge("F3", lab["F3"], y >= TH["yield_min"], f"殖利率 {_pct(y, 2)}", "≥ 3%",
                          "成長股不配息或配得少，這項天生吃虧" if y < TH["yield_min"] else ""))
    else:
        out.append(_na("F3", lab["F3"], "", "沒有殖利率資料"))

    # F4／F5：月營收
    rev = [r for r in revenue if _ok(r.get("revenue"))]
    if len(rev) >= TH["rev_high_months"]:
        window = rev[-TH["rev_high_months"]:]
        latest = window[-1]
        out.append(_judge("F4", lab["F4"], float(latest["revenue"]) >= max(float(r["revenue"]) for r in window),
                          f"{latest['month']} 營收 {_n(float(latest['revenue']) / 1e8, 1)} 億", "≥ 近 10 個月最高"))
    else:
        out.append(_na("F4", lab["F4"], "", "月營收不足 10 個月"))
    yoys = [float(r["yoy"]) for r in rev if _ok(r.get("yoy"))][-3:]
    if len(yoys) == 3:
        avg = sum(yoys) / 3
        out.append(_judge("F5", lab["F5"], avg > 0, f"近 3 月年增率平均 {avg:+.1f}%", "> 0%"))
    else:
        out.append(_na("F5", lab["F5"], "", "營收年增率資料不足 3 個月"))

    # F6–F10：財報（用最近已公布的一期）
    qs = _quarters(fin_q)
    if not qs:
        out.extend(_na(i, lab[i], "", "沒有財報資料") for i in ("F6", "F7", "F8", "F9", "F10"))
        return out
    lq = qs[-1]
    cur = fin_q[lq]

    op = cur.get("OperatingIncome")
    if _ok(op):
        out.append(_judge("F6", lab["F6"], op > 0, f"{lq} 營業利益 {_n(op / 1e8, 1)} 億", "> 0"))
    elif financial and _ok(cur.get("PreTaxIncome")):   # 金融業的損益表沒有營業利益，用稅前淨利代替
        pre = cur["PreTaxIncome"]
        out.append(_judge("F6", lab["F6"], pre > 0, f"{lq} 稅前淨利 {_n(pre / 1e8, 1)} 億", "> 0", "金融業沒有營業利益，以稅前淨利代替"))
    else:
        out.append(_na("F6", lab["F6"], "", "財報沒有營業利益欄位"))
    ni = next((cur[k] for k in NET_INCOME_KEYS if _ok(cur.get(k))), None)
    out.append(_judge("F7", lab["F7"], ni > 0, f"{lq} 稅後淨利 {_n(ni / 1e8, 1)} 億", "> 0") if _ok(ni)
               else _na("F7", lab["F7"], "", "財報沒有稅後淨利欄位"))

    eps_q = [q for q in qs if _ok(fin_q[q].get("EPS"))]
    if len(eps_q) >= 8:
        a = sum(fin_q[q]["EPS"] for q in eps_q[-4:])
        b = sum(fin_q[q]["EPS"] for q in eps_q[-8:-4])
        out.append(_judge("F8", lab["F8"], a > b, f"近四季 EPS {_n(a)} 元／前四季 {_n(b)} 元", "近四季 > 前四季"))
    else:
        out.append(_na("F8", lab["F8"], "", "財報不足 8 季"))

    out.append(_roe_item(fin_q, bs_q, financial, lab["F9"]))

    if financial:
        out.append(_na("F10", lab["F10"], "", "金融保險業沒有毛利"))
    else:
        gp, rv = cur.get("GrossProfit"), cur.get("Revenue")
        py = fin_q.get(_prev_year(lq), {})
        gp0, rv0 = py.get("GrossProfit"), py.get("Revenue")
        if all(_ok(v) for v in (gp, rv, gp0, rv0)) and rv > 0 and rv0 > 0:
            gm, gm0 = gp / rv * 100, gp0 / rv0 * 100
            out.append(_judge("F10", lab["F10"], gm >= gm0, f"{lq} {gm:.1f}%／去年同期 {gm0:.1f}%", "毛利率 ≥ 去年同期"))
        else:
            out.append(_na("F10", lab["F10"], "", "沒有去年同期的毛利資料"))
    return out


def _roe_item(fin_q: dict, bs_q: dict, financial: bool, label: str) -> dict:
    """近四季 ROE＝近四季歸屬母公司淨利 ÷ 平均（期初、期末）歸屬母公司權益。金融保險股不適用同一門檻。"""
    if financial:
        return _na("F9", label, "", "金融保險業的 ROE 門檻不同，不套用")
    qs = [q for q in _quarters(fin_q) if _ok(fin_q[q].get("EquityAttributableToOwnersOfParent")) or _ok(fin_q[q].get("IncomeAfterTaxes"))]
    if len(qs) < 4:
        return _na("F9", label, "", "財報不足 4 季")
    last4 = qs[-4:]
    ttm = sum(fin_q[q].get("EquityAttributableToOwnersOfParent", fin_q[q].get("IncomeAfterTaxes", 0)) for q in last4)
    bq = _quarters(bs_q)
    if not bq:
        return _na("F9", label, "", "沒有資產負債表資料")

    def equity(q: str) -> Optional[float]:
        row = bs_q.get(q, {})
        return row.get("EquityAttributableToOwnersOfParent", row.get("Equity"))

    e1 = equity(bq[-1])
    e0 = equity(_prev_year(bq[-1]))
    if not _ok(e1) or e1 <= 0:
        return _na("F9", label, "", "沒有權益資料")
    avg = (e0 + e1) / 2 if _ok(e0) and e0 > 0 else e1
    roe = ttm / avg * 100
    return _judge("F9", label, roe >= TH["roe_min"], f"近四季 ROE {roe:.1f}%（{last4[0]}～{last4[-1]}）", "≥ 8%")


# ═════════════════════════════════════════════════════════════════════════════
# 籌碼面（C1–C10）——全部來自免費資料；沒有券商分點
# ═════════════════════════════════════════════════════════════════════════════

_CHIP_LABELS = [
    ("C1", "外資近 5 日淨買超"),
    ("C2", "外資連買 2 日以上"),
    ("C3", "投信近 5 日淨買超"),
    ("C4", "外資、投信近 5 日有 2 日以上同日買超"),
    ("C5", "三大法人近 20 日合計淨買超"),
    ("C6", "千張大戶持股比本週增加"),
    ("C7", "集保結構偏多（大戶集中、散戶低）"),
    ("C8", "近 5 日融資餘額未增加"),
    ("C9", "近 5 日當沖比 < 30%（非投機過熱）"),
    ("C10", "外資持股比例近 20 日上升"),
]


def _series(flow: list[dict]) -> list[float]:
    return [float(r["net"]) for r in (flow or []) if _ok(r.get("net"))]


def chip_checks(chip: Optional[dict], holding: Optional[list[dict]] = None) -> list[dict]:
    lab = dict(_CHIP_LABELS)
    major = (chip or {}).get("major_players") or {}
    inst = major.get("institutional_flow") or {}
    foreign, trust, dealer = _series(inst.get("foreign")), _series(inst.get("trust")), _series(inst.get("dealer"))
    out: list[dict] = []

    def lots(x: float) -> str:  # 股 → 張
        return f"{x / 1000:+,.0f} 張"

    if len(foreign) >= 5:
        s5 = sum(foreign[-5:])
        out.append(_judge("C1", lab["C1"], s5 > 0, f"近 5 日 {lots(s5)}", "> 0"))
    else:
        out.append(_na("C1", lab["C1"], "", "法人資料不足"))
    if len(foreign) >= 2:
        out.append(_judge("C2", lab["C2"], foreign[-1] > 0 and foreign[-2] > 0, f"最近兩日 {lots(foreign[-2])}／{lots(foreign[-1])}", "連 2 日買超"))
    else:
        out.append(_na("C2", lab["C2"], "", "法人資料不足"))
    if len(trust) >= 5:
        s5 = sum(trust[-5:])
        out.append(_judge("C3", lab["C3"], s5 > 0, f"近 5 日 {lots(s5)}", "> 0"))
    else:
        out.append(_na("C3", lab["C3"], "", "法人資料不足"))

    sync = (chip or {}).get("sync_buy") or {}
    daily = (sync.get("daily") or [])[-5:]
    if len(daily) >= 5:
        both = sum(1 for r in daily if r.get("sync") == "buy")
        out.append(_judge("C4", lab["C4"], both >= 2, f"近 5 日同步買超 {both} 日", "≥ 2 日"))
    else:
        out.append(_na("C4", lab["C4"], "", "外資或投信資料不足"))

    if len(foreign) >= 20 and len(trust) >= 20 and len(dealer) >= 20:
        s20 = sum(foreign[-20:]) + sum(trust[-20:]) + sum(dealer[-20:])
        out.append(_judge("C5", lab["C5"], s20 > 0, f"近 20 日 {lots(s20)}", "> 0"))
    else:
        out.append(_na("C5", lab["C5"], "", "法人資料不足 20 日"))

    dist = (chip or {}).get("distribution") or {}
    moves = dist.get("movements") or []
    if moves and _ok(moves[-1].get("mega_pct_change")):
        ch = float(moves[-1]["mega_pct_change"])
        out.append(_judge("C6", lab["C6"], ch > 0, f"千張大戶本週 {ch:+.2f}%（{moves[-1].get('date', '')}）", "> 0"))
    else:
        out.append(_na("C6", lab["C6"], "", "集保資料不足（需要至少兩週）"))
    if dist.get("verdict"):
        out.append(_judge("C7", lab["C7"], dist["verdict"] in ("籌碼集中", "偏多"), f"集保判定「{dist['verdict']}」", "判定為「籌碼集中」或「偏多」"))
    else:
        out.append(_na("C7", lab["C7"], "", "沒有集保資料"))

    mdata = (major.get("margin_analysis") or {}).get("data") or []
    if len(mdata) >= 6:
        a, b = mdata[-1].get("margin_balance"), mdata[-6].get("margin_balance")
        out.append(_judge("C8", lab["C8"], _ok(a) and _ok(b) and a <= b, f"融資餘額 {_n(b, 0)} → {_n(a, 0)} 張", "最新 ≤ 5 日前"))
    else:
        out.append(_na("C8", lab["C8"], "", "沒有融資資料（可能不是融資標的）"))

    dt = (chip or {}).get("day_trade") or {}
    if _ok(dt.get("ratio_5d")):
        out.append(_judge("C9", lab["C9"], float(dt["ratio_5d"]) < TH["daytrade_max"], f"近 5 日當沖比 {_pct(dt['ratio_5d'])}", "< 30%"))
    else:
        out.append(_na("C9", lab["C9"], "", "沒有當沖資料"))

    h = [r for r in (holding or []) if _ok(r.get("ratio"))]
    if len(h) >= 15:
        a, b = float(h[-1]["ratio"]), float(h[-min(len(h), 21)]["ratio"])
        out.append(_judge("C10", lab["C10"], a > b, f"外資持股 {b:.2f}% → {a:.2f}%", "上升"))
    else:
        out.append(_na("C10", lab["C10"], "", "外資持股資料不足"))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 旗標（只警示、不計分）
# ═════════════════════════════════════════════════════════════════════════════

def build_flags(frame: Optional[pd.DataFrame], bs_q: dict, cf_q: dict, chip: Optional[dict]) -> list[dict]:
    flags: list[dict] = []

    # 負債比
    bq = _quarters(bs_q)
    if bq:
        row = bs_q[bq[-1]]
        liab, assets = row.get("Liabilities"), row.get("TotalAssets")
        if _ok(liab) and _ok(assets) and assets > 0 and liab / assets * 100 > TH["debt_warn"]:
            flags.append({"id": "debt_high", "tone": "warn", "text": f"負債比 {liab / assets * 100:.1f}%（{bq[-1]}），高於 {TH['debt_warn']:.0f}%；金融業與重資本產業本來就高，請對照同業。"})

    # 營業現金流（現金流量表是當年累計）
    cq = _quarters(cf_q)
    if cq:
        row = cf_q[cq[-1]]
        ocf = next((row[k] for k in ("NetCashInflowFromOperatingActivities", "CashFlowsFromOperatingActivities") if _ok(row.get(k))), None)
        if _ok(ocf) and ocf < 0:
            flags.append({"id": "ocf_negative", "tone": "warn", "text": f"{cq[-1]} 營業活動現金流為負（當年累計 {ocf / 1e8:,.1f} 億），獲利沒有變成現金，留意應收帳款與存貨。"})

    if frame is not None and len(frame):
        last = frame.iloc[-1]
        close, ma20, rsi = last.get("close"), last.get("ma20"), last.get("rsi14")
        hot = []
        if _ok(rsi) and rsi > TH["overheat_rsi"]:
            hot.append(f"RSI {rsi:.0f}")
        if _ok(close) and _ok(ma20) and ma20 > 0 and close > ma20 * (1 + TH["overheat_ma20"]):
            hot.append(f"收盤高於 20 日線 {(close / ma20 - 1) * 100:.0f}%")
        if hot:
            flags.append({"id": "overextended", "tone": "warn", "text": "短線乖離偏大（" + "、".join(hot) + "），追價風險較高。"})
        ma240 = frame["ma240"] if "ma240" in frame else None
        if ma240 is not None and len(ma240) > 21 and _ok(ma240.iloc[-1]) and _ok(ma240.iloc[-21]) and _ok(close):
            above = close > ma240.iloc[-1]
            rising = ma240.iloc[-1] > ma240.iloc[-21]
            if above and rising:
                flags.append({"id": "above_ma240", "tone": "info", "text": "站上年線且年線上揚（長線趨勢向上）。"})
            elif not above:
                flags.append({"id": "below_ma240", "tone": "warn", "text": "收盤在年線之下（長線趨勢偏弱）。"})

    dt = (chip or {}).get("day_trade") or {}
    if dt.get("verdict") == "投機極熱":
        flags.append({"id": "daytrade_hot", "tone": "warn", "text": f"當沖比過高（近 5 日 {_pct(dt.get('ratio_5d'))}），短線投機氣氛濃。"})
    mr = (chip or {}).get("margin_ratio") or {}
    risk = str(mr.get("risk", ""))
    if "斷頭" in risk or "偏低" in risk:
        flags.append({"id": "margin_low", "tone": "warn", "text": f"融資維持率估算：{risk}。"})
    return flags


# ═════════════════════════════════════════════════════════════════════════════
# 彙總
# ═════════════════════════════════════════════════════════════════════════════

def summarize(key: str, label: str, items: list[dict], period: str = "") -> dict:
    decidable = [i for i in items if i["status"] != NA]
    passed = sum(1 for i in items if i["status"] == PASS)
    score10 = round(passed / len(decidable) * 10, 1) if len(decidable) >= MIN_DECIDABLE else None
    return {
        "key": key, "label": label, "items": items, "passed": passed, "decidable": len(decidable),
        "total": len(items), "score10": score10,
        "score100": round(score10 * 10) if score10 is not None else None,
        "period": period,
    }


def classify(dims: dict[str, dict]) -> dict:
    """依三面向分數（0–10）判定標籤。規則可解釋，且一律是現況描述。"""
    b, t, c = (dims[k]["score10"] for k in ("fundamental", "technical", "chip"))
    note = "現況描述，不是預測；門檻尚未經回測驗證。"
    if None in (b, t, c):
        missing = [dims[k]["label"] for k in ("fundamental", "technical", "chip") if dims[k]["score10"] is None]
        return {"text": "資料不足", "tone": "flat", "note": f"{'、'.join(missing)}可判定的項目太少。{note}"}
    total = b + t + c
    if min(b, t, c) >= 6 and total >= 20:
        return {"text": "面面俱到・強勢", "tone": "up", "note": note}
    if b >= 7 and t < 5:
        return {"text": "體質佳・等待進場", "tone": "flat", "note": note}
    if t >= 6 and b < 5:
        return {"text": "短線強、體質弱・小部位", "tone": "warn", "note": note}
    if b < 4:
        return {"text": "體質疑慮・避開", "tone": "down", "note": note}
    return {"text": "訊號分歧", "tone": "flat", "note": note}


def compute_scorecard(data: dict) -> dict:
    """純計算（不碰網路）：把整理好的資料算成評分卡。data 的欄位見 build_scorecard。"""
    frame = compute_technical_frame(data.get("bars") or [])
    fund = fundamental_checks(data.get("per") or [], data.get("revenue") or [], data.get("fin_q") or {},
                              data.get("bs_q") or {}, data.get("industry", ""))
    tech = technical_checks(data.get("bars") or [], data.get("taiex"), frame)
    chip = chip_checks(data.get("chip"), data.get("holding"))

    fin_qs = _quarters(data.get("fin_q") or {})
    rev = data.get("revenue") or []
    dims = {
        "fundamental": summarize("fundamental", "基本面", fund, fin_qs[-1] if fin_qs else ""),
        "technical": summarize("technical", "技術面", tech, str((data.get("bars") or [{}])[-1].get("date", ""))[:10]),
        "chip": summarize("chip", "籌碼面", chip, ""),
    }
    decidable = sum(d["decidable"] for d in dims.values())
    passed = sum(d["passed"] for d in dims.values())
    scored = [d["score10"] for d in dims.values() if d["score10"] is not None]
    return {
        "version": SCORECARD_VERSION,
        "applicable": True,
        "dimensions": [dims["fundamental"], dims["technical"], dims["chip"]],
        "total": {
            "passed": passed, "decidable": decidable, "total": 30,
            "score30": round(sum(scored), 1) if len(scored) == 3 else None,
        },
        "label": classify(dims),
        # 給個股分析頁的「AI 決策評分」用：通過率換成 0–100；資料不足就是 None（前端當中性 50）
        "scores": {k: dims[k]["score100"] for k in ("technical", "fundamental", "chip")},
        "flags": build_flags(frame, data.get("bs_q") or {}, data.get("cf_q") or {}, data.get("chip")),
        "meta": {
            "financial_period": fin_qs[-1] if fin_qs else None,
            "revenue_month": rev[-1]["month"] if rev else None,
            "price_date": str((data.get("bars") or [{}])[-1].get("date", ""))[:10] or None,
            "industry": data.get("industry", ""),
            "chip_available": bool(data.get("chip")),
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# 取資料＋組裝（唯一碰網路的地方）
# ═════════════════════════════════════════════════════════════════════════════

# 一次未命中快取大約打 FinMind 14 次：日線、加權指數、PER、營收、損益、資產負債、現金流、外資持股、
# 股票基本資料，加上籌碼分析（法人、融資、當沖、籌碼用的日線）。API 層用這個數字扣額度。
FETCH_COST = 14
CHIP_TIMEOUT_SECONDS = 60


def _records(df: Optional[pd.DataFrame], cols: dict[str, str]) -> list[dict]:
    """DataFrame → [{新欄位: 值}]，只保留存在的欄位；date 一律轉成 'YYYY-MM-DD'。"""
    if df is None or df.empty:
        return []
    keep = {src: dst for src, dst in cols.items() if src in df.columns}
    if "date" in df.columns:
        df = df.sort_values("date")
    rows = []
    for rec in df.to_dict("records"):
        row = {dst: rec[src] for src, dst in keep.items()}
        if "date" in row:
            row["date"] = str(row["date"])[:10]
        rows.append(row)
    return rows


async def build_scorecard(symbol: str) -> dict:
    """抓資料並算出評分卡。查無日線時丟 ValueError；其他資料取不到只讓對應項目變「不適用」，
    並在 meta.failed 列出（API 層看到有失敗就不快取，避免把額度用盡的殘缺結果存 6 小時）。"""
    import asyncio
    import logging
    from datetime import date, timedelta

    from ..crawler import FinMindClient, FundamentalCrawler, StockPriceCrawler
    from ..crawler.fundamental import pivot_quarters

    log = logging.getLogger(__name__)
    today = date.today()
    end = today.isoformat()
    ago = lambda days: (today - timedelta(days=days)).isoformat()  # noqa: E731
    fm = FinMindClient()
    sem = asyncio.Semaphore(5)

    async def bars():
        df = await StockPriceCrawler().get_price(symbol, ago(430), end)
        return _records(df, {"date": "date", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})

    async def taiex():
        return _records(await fm.get_stock_price("TAIEX", ago(40), end), {"date": "date", "close": "close"})

    async def per():
        return _records(await fm.get_valuation(symbol, ago(365 * 3 + 20), end),
                        {"date": "date", "PER": "PER", "PBR": "PBR", "dividend_yield": "dividend_yield"})

    async def revenue():
        return await FundamentalCrawler().get_monthly_revenue(symbol, ago(800), end)

    async def fin():
        return pivot_quarters(await fm.get_financial_statements(symbol, ago(365 * 3 + 120), end))

    async def bs():
        return pivot_quarters(await fm.get_balance_sheet(symbol, ago(365 * 2 + 120), end))

    async def cf():
        return pivot_quarters(await fm.get_cash_flows(symbol, ago(365 + 120), end))

    async def holding():
        return _records(await fm.get_shares_outstanding(symbol, ago(60), end), {"date": "date", "ForeignInvestmentSharesRatio": "ratio"})

    async def info():
        df = await fm.get_stock_info()
        if df is None or df.empty:
            return {}
        hit = df[df["stock_id"].astype(str) == symbol]
        if hit.empty:
            return {}
        row = hit.iloc[0]
        return {"name": str(row.get("stock_name", "") or ""), "industry": str(row.get("industry_category", "") or "")}

    async def chip():
        from ..api.chip import _build_chip_analysis  # 延後 import：避免 api ↔ analysis 循環
        # 籌碼分析含集保（TDCC）下載，來源連不上時每次可能卡 90 秒、重試 3 次；
        # 這裡設上限，逾時就只讓籌碼面的項目變「不適用」，不要整張評分卡等幾分鐘。
        return await asyncio.wait_for(_build_chip_analysis(symbol, 90), timeout=CHIP_TIMEOUT_SECONDS)

    async def guarded(coro_fn):
        async with sem:
            return await coro_fn()

    names = ["bars", "taiex", "per", "revenue", "fin", "bs", "cf", "holding", "info", "chip"]
    fns = [bars, taiex, per, revenue, fin, bs, cf, holding, info, chip]
    results = await asyncio.gather(*[guarded(f) for f in fns], return_exceptions=True)
    got: dict[str, Any] = {}
    failed: list[str] = []
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            log.warning("scorecard: %s unavailable for %s (%s)", name, symbol, type(res).__name__)
            failed.append(name)
            got[name] = None
        else:
            got[name] = res

    if not got["bars"]:
        raise ValueError("查無日線資料（代碼錯誤或尚未上市）")

    inf = got["info"] or {}
    industry = inf.get("industry", "")
    if industry.upper() in ("ETF", "ETN"):
        return {"version": SCORECARD_VERSION, "applicable": False, "symbol": symbol, "name": inf.get("name", ""),
                "reason": "ETF 沒有財報與個股籌碼，請改用「ETF 比較」頁。"}

    chip_data = got["chip"] if isinstance(got["chip"], dict) else None
    result = compute_scorecard({
        "bars": got["bars"], "taiex": got["taiex"], "per": got["per"] or [], "revenue": got["revenue"] or [],
        "fin_q": got["fin"] or {}, "bs_q": got["bs"] or {}, "cf_q": got["cf"] or {},
        "holding": got["holding"], "chip": chip_data, "industry": industry,
    })
    result.update({"symbol": symbol, "name": inf.get("name", "")})
    result["meta"]["failed"] = failed
    return result
