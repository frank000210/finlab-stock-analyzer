"""個股三面向評分卡：每個檢核項的邊界值、不適用規則、彙總與標籤、API 的快取與額度。

純計算（stock_scorecard.py）用合成資料手算；API 層用假快取、假計數器、假 build_scorecard，
不碰 FinMind／MongoDB。另外鎖住兩個既有資料缺陷的修正（淨利、負債比）。
"""

import asyncio
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analysis import stock_scorecard as sc
from app.crawler.fundamental import FundamentalCrawler, pivot_quarters, quarter_label

PASS, FAIL, NA = sc.PASS, sc.FAIL, sc.NA


# ── 合成資料 ────────────────────────────────────────────────────────────────

def make_bars(closes, vols=None, start="2025-01-02"):
    d0 = date.fromisoformat(start)
    out = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        out.append({
            "date": (d0 + timedelta(days=i)).isoformat(), "open": prev, "high": max(c, prev) * 1.01,
            "low": min(c, prev) * 0.99, "close": float(c), "volume": float(vols[i] if vols else 1000),
        })
    return out


def by_id(items):
    return {i["id"]: i for i in items}


# ═════════════════════════════════════════════════════════════════════════════
# 技術面
# ═════════════════════════════════════════════════════════════════════════════

def test_technical_uptrend_passes_trend_items_and_fails_overheat_and_signals():
    bars = make_bars([100 + i for i in range(120)])
    r = by_id(sc.technical_checks(bars))
    assert [r[k]["status"] for k in ("T1", "T2", "T3", "T4", "T5")] == [PASS] * 5
    assert r["T6"]["status"] == FAIL            # 一路上漲，RSI 在 70 以上＝過熱
    assert r["T7"]["status"] == FAIL            # 沒有黃金交叉
    assert r["T8"]["status"] == FAIL            # 量沒放大
    assert r["T10"]["status"] == PASS           # 收盤就是 60 日最高
    assert r["T9"]["status"] == NA              # 沒給加權指數
    assert len(r) == 10 and all(set(i) >= {"id", "label", "status", "value", "threshold"} for i in r.values())


def test_technical_downtrend_fails_trend_items():
    r = by_id(sc.technical_checks(make_bars([300 - i for i in range(120)])))
    assert [r[k]["status"] for k in ("T1", "T2", "T3", "T4", "T5", "T10")] == [FAIL] * 6


def test_technical_all_na_when_history_too_short():
    out = sc.technical_checks(make_bars([100 + i for i in range(20)]))
    assert len(out) == 10 and {i["status"] for i in out} == {NA}


def test_technical_na_when_ma60_not_yet_available():
    r = by_id(sc.technical_checks(make_bars([100 + i * 0.1 for i in range(40)])))
    assert r["T3"]["status"] == NA and r["T1"]["status"] == PASS   # 40 根夠算 5/10/20MA，不夠 60MA
    assert r["T10"]["status"] == NA                                # 不足 60 根


@pytest.mark.parametrize("rsi,want", [(50.0, PASS), (70.0, PASS), (49.99, FAIL), (70.01, FAIL)])
def test_rsi_band_boundaries(rsi, want):
    bars = make_bars([100 + i * 0.5 for i in range(80)])
    frame = sc.compute_technical_frame(bars)
    frame.loc[frame.index[-1], "rsi14"] = rsi
    assert by_id(sc.technical_checks(bars, None, frame))["T6"]["status"] == want


def test_golden_cross_within_three_days_and_k_below_80():
    bars = make_bars([100 + i * 0.5 for i in range(80)])
    frame = sc.compute_technical_frame(bars)
    n = len(frame)

    def set_kd(prev_k, prev_d, k, d):
        frame["k"] = 50.0
        frame["d"] = 50.0
        frame.loc[n - 3, ["k", "d"]] = [prev_k, prev_d]   # 前一日 K ≤ D
        frame.loc[n - 2, ["k", "d"]] = [k, d]             # 當日 K > D → 黃金交叉
        frame.loc[n - 1, ["k", "d"]] = [k, d]

    set_kd(40, 45, 50, 48)
    assert by_id(sc.technical_checks(bars, None, frame))["T7"]["status"] == PASS
    set_kd(75, 80, 85, 82)   # 交叉了，但 K ≥ 80（高檔鈍化）
    assert by_id(sc.technical_checks(bars, None, frame))["T7"]["status"] == FAIL
    frame["k"], frame["d"] = 60.0, 50.0                        # K 一直在 D 上、沒有「交叉」動作
    assert by_id(sc.technical_checks(bars, None, frame))["T7"]["status"] == FAIL


def test_volume_up_and_close_up():
    closes = [100 + i * 0.1 for i in range(80)]
    vols = [1000] * 79 + [2500]
    assert by_id(sc.technical_checks(make_bars(closes, vols)))["T8"]["status"] == PASS
    closes2 = closes[:-1] + [closes[-2] - 1]                 # 放量但收跌
    assert by_id(sc.technical_checks(make_bars(closes2, vols)))["T8"]["status"] == FAIL
    assert by_id(sc.technical_checks(make_bars(closes, [0] * 80)))["T8"]["status"] == NA   # 均量為 0


def test_relative_to_market_needs_matching_dates():
    bars = make_bars([100 + i for i in range(60)])
    dates = [b["date"] for b in bars]
    strong = [{"date": d, "close": 1000 + 0.5 * i} for i, d in enumerate(dates)]     # 大盤漲得比個股少
    weak = [{"date": d, "close": 1000 + 50 * i} for i, d in enumerate(dates)]        # 大盤漲更多
    assert by_id(sc.technical_checks(bars, strong))["T9"]["status"] == PASS
    assert by_id(sc.technical_checks(bars, weak))["T9"]["status"] == FAIL
    shifted = [{"date": f"2030-01-{i % 28 + 1:02d}", "close": 1000.0} for i in range(60)]
    assert by_id(sc.technical_checks(bars, shifted))["T9"]["status"] == NA


# ═════════════════════════════════════════════════════════════════════════════
# 基本面
# ═════════════════════════════════════════════════════════════════════════════

def per_rows(n=200, per=20.0, pbr=3.0, y=2.0, last=None):
    rows = [{"date": f"2026-01-{(i % 28) + 1:02d}", "PER": per, "PBR": pbr, "dividend_yield": y} for i in range(n)]
    if last:
        rows[-1] = {**rows[-1], **last}
    return rows


def revenue_rows(vals, yoy=10.0):
    return [{"month": f"2026-{i + 1:02d}", "revenue": v * 1e8, "yoy": yoy} for i, v in enumerate(vals)]


def quarters_fin(n=12, op=100e8, ni=80e8, eps=2.0, gp=500e8, rev=1000e8, last_year_gm=None):
    """n 季的損益表（最後一季是 2026Q2）。last_year_gm 給了就覆蓋去年同期（2025Q2）的毛利率。"""
    out = {}
    y, q = 2026, 2
    for _ in range(n):
        out[f"{y}Q{q}"] = {"Revenue": rev, "GrossProfit": gp, "OperatingIncome": op, "IncomeAfterTaxes": ni,
                           "EquityAttributableToOwnersOfParent": ni, "EPS": eps}
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    if last_year_gm is not None:
        out["2025Q2"] = {**out["2025Q2"], "GrossProfit": rev * last_year_gm / 100}
    return out


def quarters_bs(equity=1000e8, n=6):
    out = {}
    y, q = 2026, 2
    for _ in range(n):
        out[f"{y}Q{q}"] = {"EquityAttributableToOwnersOfParent": equity, "Equity": equity,
                           "Liabilities": equity * 0.5, "TotalAssets": equity * 1.5}
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return out


def test_valuation_relative_to_own_history_and_losses():
    base = lambda **kw: by_id(sc.fundamental_checks(per_rows(**kw), [], {}, {}))   # noqa: E731
    assert base(last={"PER": 15.0, "PBR": 2.0})["F1"]["status"] == PASS
    assert base(last={"PER": 15.0, "PBR": 2.0})["F2"]["status"] == PASS
    r = base(last={"PER": 25.0, "PBR": 4.0})
    assert r["F1"]["status"] == FAIL and r["F2"]["status"] == FAIL
    assert base(last={"PER": 20.0})["F1"]["status"] == PASS                         # 剛好等於中位數
    loss = base(last={"PER": 0, "PBR": 2.0})["F1"]                                    # 虧損股 PER 為 0
    assert loss["status"] == FAIL and "虧損" in loss["value"]
    assert base(n=50)["F1"]["status"] == NA                                           # 歷史不足 100 日


@pytest.mark.parametrize("y,want", [(3.0, PASS), (2.99, FAIL), (0.0, FAIL), (6.5, PASS)])
def test_dividend_yield_threshold(y, want):
    assert by_id(sc.fundamental_checks(per_rows(last={"dividend_yield": y}), [], {}, {}))["F3"]["status"] == want


def test_dividend_yield_na_without_data():
    rows = [{"date": "2026-01-01", "PER": 20.0, "PBR": 2.0}] * 150
    assert by_id(sc.fundamental_checks(rows, [], {}, {}))["F3"]["status"] == NA


def test_revenue_new_high_and_yoy():
    up = revenue_rows([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
    r = by_id(sc.fundamental_checks([], up, {}, {}))
    assert r["F4"]["status"] == PASS and r["F5"]["status"] == PASS
    down = revenue_rows([10, 11, 12, 13, 14, 30, 16, 17, 18, 19, 20], yoy=-5)   # 近 10 個月內有更高的 30
    r = by_id(sc.fundamental_checks([], down, {}, {}))
    assert r["F4"]["status"] == FAIL and r["F5"]["status"] == FAIL
    assert by_id(sc.fundamental_checks([], revenue_rows([1, 2, 3]), {}, {}))["F4"]["status"] == NA


def test_financial_statement_items_and_period_label():
    r = by_id(sc.fundamental_checks([], [], quarters_fin(), quarters_bs()))
    assert [r[k]["status"] for k in ("F6", "F7")] == [PASS, PASS]
    assert "2026Q2" in r["F6"]["value"]
    assert r["F8"]["status"] == FAIL                         # 每季 EPS 都 2.0，近四季不大於前四季
    loss = quarters_fin(op=-5e8, ni=-3e8)
    r = by_id(sc.fundamental_checks([], [], loss, quarters_bs()))
    assert [r[k]["status"] for k in ("F6", "F7")] == [FAIL, FAIL]


def test_eps_growth_needs_eight_quarters():
    fin = quarters_fin(n=8)
    for i, q in enumerate(sorted(fin)):
        fin[q]["EPS"] = 1.0 if i < 4 else 2.0                 # 前四季 1.0、近四季 2.0
    assert by_id(sc.fundamental_checks([], [], fin, {}))["F8"]["status"] == PASS
    assert by_id(sc.fundamental_checks([], [], quarters_fin(n=6), {}))["F8"]["status"] == NA


@pytest.mark.parametrize("equity,want", [(1000e8, PASS), (4000e8, FAIL)])
def test_roe_ttm_over_average_equity(equity, want):
    # 近四季淨利 4 × 25 億 ＝ 100 億；平均權益 1,000 億 → ROE 10%；4,000 億 → 2.5%
    fin = quarters_fin(ni=25e8)
    item = by_id(sc.fundamental_checks([], [], fin, quarters_bs(equity)))["F9"]
    assert item["status"] == want
    assert ("10.0%" in item["value"]) if want == PASS else ("2.5%" in item["value"])


def test_gross_margin_vs_same_quarter_last_year():
    better = by_id(sc.fundamental_checks([], [], quarters_fin(last_year_gm=40), {}))["F10"]     # 今年 50%、去年 40%
    worse = by_id(sc.fundamental_checks([], [], quarters_fin(last_year_gm=60), {}))["F10"]
    assert better["status"] == PASS and worse["status"] == FAIL
    assert by_id(sc.fundamental_checks([], [], quarters_fin(n=3), {}))["F10"]["status"] == NA   # 沒有去年同期


def test_financial_industry_skips_roe_and_gross_margin():
    r = by_id(sc.fundamental_checks([], [], quarters_fin(), quarters_bs(), industry="金融保險業"))
    assert r["F9"]["status"] == NA and r["F10"]["status"] == NA
    assert sc.is_financial_industry("金融保險業") and sc.is_financial_industry("銀行業")
    assert not sc.is_financial_industry("半導體業")


def test_financial_industry_income_fields_use_pretax_and_singular_after_tax():
    fin = {f"2026Q{i}": {"EPS": 2.0, "PreTaxIncome": 50e8, "IncomeAfterTax": 40e8, "Revenue": 100e8} for i in (1, 2)}
    r = by_id(sc.fundamental_checks([], [], fin, {}, industry="金融保險"))
    assert r["F6"]["status"] == PASS and "稅前淨利" in r["F6"]["value"] and "代替" in r["F6"]["note"]
    assert r["F7"]["status"] == PASS and "稅後淨利" in r["F7"]["value"]
    # 一般公司沒有營業利益欄位就是不適用，不會偷偷用稅前淨利代替
    assert by_id(sc.fundamental_checks([], [], fin, {}, industry="半導體業"))["F6"]["status"] == NA


def test_fundamentals_all_na_without_any_data():
    out = sc.fundamental_checks([], [], {}, {})
    assert len(out) == 10 and {i["status"] for i in out} == {NA}


# ═════════════════════════════════════════════════════════════════════════════
# 籌碼面
# ═════════════════════════════════════════════════════════════════════════════

def flow(vals):
    return [{"date": f"2026-10-{i + 1:02d}", "net": v} for i, v in enumerate(vals)]


def chip_data(foreign=None, trust=None, dealer=None, sync=None, mega=0.5, verdict="偏多", margin=None, dt=5.0):
    n = 25
    return {
        "major_players": {
            "institutional_flow": {"foreign": flow(foreign or [1000] * n), "trust": flow(trust or [500] * n), "dealer": flow(dealer or [100] * n)},
            "margin_analysis": {"data": [{"date": f"d{i}", "margin_balance": v, "short_balance": 0} for i, v in enumerate(margin or [100] * 10)]},
        },
        "sync_buy": {"daily": [{"date": f"d{i}", "sync": s} for i, s in enumerate(sync or ["buy"] * 10)]},
        "distribution": {"movements": [{"date": "20261106", "mega_pct_change": mega}], "verdict": verdict},
        "day_trade": {"ratio_5d": dt},
    }


def holding_rows(a, b, n=25):
    rows = [{"date": f"d{i}", "ratio": a} for i in range(n - 1)]
    return rows + [{"date": "last", "ratio": b}]


def test_chip_all_pass():
    r = by_id(sc.chip_checks(chip_data(), holding_rows(60.0, 61.0)))
    assert [r[f"C{i}"]["status"] for i in range(1, 11)] == [PASS] * 10


def test_chip_foreign_and_trust_rules():
    f = [1000] * 18 + [-5000, 100]                         # 最近兩日不是都買超；近 5 日合計為負
    r = by_id(sc.chip_checks(chip_data(foreign=f), None))
    assert r["C1"]["status"] == FAIL
    f2 = [-100] * 23 + [10, 20]
    assert by_id(sc.chip_checks(chip_data(foreign=f2), None))["C2"]["status"] == PASS
    assert by_id(sc.chip_checks(chip_data(foreign=[100] * 23 + [-10, 20]), None))["C2"]["status"] == FAIL
    assert by_id(sc.chip_checks(chip_data(trust=[-1] * 25), None))["C3"]["status"] == FAIL


def test_chip_sync_buy_needs_two_days_in_last_five():
    ok = by_id(sc.chip_checks(chip_data(sync=["none"] * 5 + ["buy", "none", "buy", "none", "none"]), None))["C4"]
    no = by_id(sc.chip_checks(chip_data(sync=["buy"] * 5 + ["none"] * 4 + ["buy"]), None))["C4"]
    assert ok["status"] == PASS and no["status"] == FAIL


def test_chip_twenty_day_total_and_distribution():
    big_sell = by_id(sc.chip_checks(chip_data(foreign=[-1000] * 25), None))
    assert big_sell["C5"]["status"] == FAIL
    assert by_id(sc.chip_checks(chip_data(mega=-0.2), None))["C6"]["status"] == FAIL
    assert by_id(sc.chip_checks(chip_data(mega=0.0), None))["C6"]["status"] == FAIL           # 沒增加就不算
    assert by_id(sc.chip_checks(chip_data(verdict="籌碼集中"), None))["C7"]["status"] == PASS
    assert by_id(sc.chip_checks(chip_data(verdict="中性"), None))["C7"]["status"] == FAIL


def test_chip_margin_daytrade_and_foreign_holding():
    assert by_id(sc.chip_checks(chip_data(margin=[100] * 4 + [100, 110, 120, 130, 140, 150]), None))["C8"]["status"] == FAIL
    assert by_id(sc.chip_checks(chip_data(margin=[100, 110, 120, 130, 140, 150, 140, 130, 120, 100]), None))["C8"]["status"] == PASS
    assert by_id(sc.chip_checks(chip_data(dt=30.0), None))["C9"]["status"] == FAIL           # 剛好 30% 不算「< 30%」
    assert by_id(sc.chip_checks(chip_data(dt=29.9), None))["C9"]["status"] == PASS
    assert by_id(sc.chip_checks(chip_data(), holding_rows(61.0, 60.5)))["C10"]["status"] == FAIL
    assert by_id(sc.chip_checks(chip_data(), holding_rows(61.0, 61.0)))["C10"]["status"] == FAIL   # 持平不算上升
    assert by_id(sc.chip_checks(chip_data(), holding_rows(61.0, 61.0, n=10)))["C10"]["status"] == NA


def test_chip_all_na_without_chip_bundle():
    out = sc.chip_checks(None, None)
    assert len(out) == 10 and {i["status"] for i in out} == {NA}


# ═════════════════════════════════════════════════════════════════════════════
# 旗標、彙總、標籤
# ═════════════════════════════════════════════════════════════════════════════

def test_flags_debt_cashflow_overheat_and_ma240():
    bs = {"2026Q2": {"Liabilities": 700.0, "TotalAssets": 1000.0}}
    cf = {"2026Q2": {"NetCashInflowFromOperatingActivities": -5e8}}
    bars = make_bars([100 + i * 0.5 for i in range(300)])
    frame = sc.compute_technical_frame(bars)
    flags = {f["id"]: f for f in sc.build_flags(frame, bs, cf, {"day_trade": {"verdict": "投機極熱", "ratio_5d": 45.0},
                                                                "margin_ratio": {"risk": "維持率偏低"}})}
    assert {"debt_high", "ocf_negative", "daytrade_hot", "margin_low", "above_ma240"} <= set(flags)
    assert flags["above_ma240"]["tone"] == "info" and flags["debt_high"]["tone"] == "warn"
    down = sc.compute_technical_frame(make_bars([400 - i for i in range(300)]))
    assert "below_ma240" in {f["id"] for f in sc.build_flags(down, {}, {}, None)}
    assert sc.build_flags(None, {}, {}, None) == []


def test_summarize_scales_by_decidable_items_and_hides_thin_dimensions():
    items = [{"status": PASS}] * 6 + [{"status": FAIL}] * 3 + [{"status": NA}]
    s = sc.summarize("technical", "技術面", items)
    assert (s["passed"], s["decidable"], s["score10"], s["score100"]) == (6, 9, 6.7, 67)
    thin = sc.summarize("chip", "籌碼面", [{"status": PASS}] * 4 + [{"status": NA}] * 6)
    assert thin["score10"] is None and thin["score100"] is None and thin["decidable"] == 4


def dims(b, t, c):
    mk = lambda key, label, v: {"key": key, "label": label, "score10": v}   # noqa: E731
    return {"fundamental": mk("fundamental", "基本面", b), "technical": mk("technical", "技術面", t), "chip": mk("chip", "籌碼面", c)}


@pytest.mark.parametrize("b,t,c,text", [
    (8, 7, 6, "面面俱到・強勢"),
    (6, 6, 8, "面面俱到・強勢"),          # 總分 20 且三面向都 ≥ 6
    (6, 6, 6, "訊號分歧"),                # 總分 18 < 20
    (7, 4, 5, "體質佳・等待進場"),
    (3, 8, 9, "短線強、體質弱・小部位"),
    (3, 3, 3, "體質疑慮・避開"),
    (5, 5, 5, "訊號分歧"),
])
def test_classify(b, t, c, text):
    label = sc.classify(dims(b, t, c))
    assert label["text"] == text and "不是預測" in label["note"]


def test_classify_needs_all_three_dimensions():
    label = sc.classify(dims(8, None, 6))
    assert label["text"] == "資料不足" and "技術面" in label["note"]


def test_compute_scorecard_end_to_end():
    bars = make_bars([100 + i for i in range(120)])
    card = sc.compute_scorecard({
        "bars": bars, "taiex": None, "per": per_rows(last={"PER": 15.0, "PBR": 2.0, "dividend_yield": 4.0}),
        "revenue": revenue_rows([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]),
        "fin_q": quarters_fin(ni=25e8), "bs_q": quarters_bs(), "cf_q": {}, "chip": chip_data(),
        "holding": holding_rows(60.0, 61.0), "industry": "半導體業",
    })
    f, t, c = card["dimensions"]
    assert (f["key"], t["key"], c["key"]) == ("fundamental", "technical", "chip")
    assert all(d["total"] == 10 and len(d["items"]) == 10 for d in card["dimensions"])
    assert c["passed"] == 10 and c["score10"] == 10.0
    assert card["total"]["passed"] == sum(d["passed"] for d in card["dimensions"])
    assert card["total"]["decidable"] == sum(d["decidable"] for d in card["dimensions"])
    assert card["scores"] == {"technical": t["score100"], "fundamental": f["score100"], "chip": c["score100"]}
    assert card["meta"]["financial_period"] == "2026Q2" and card["meta"]["revenue_month"] == "2026-11"
    assert card["label"]["text"] and card["applicable"] is True


def test_compute_scorecard_marks_missing_sections_na_instead_of_zero():
    card = sc.compute_scorecard({"bars": make_bars([100 + i for i in range(120)])})
    f, t, c = card["dimensions"]
    assert f["decidable"] == 0 and c["decidable"] == 0 and f["score10"] is None and c["score10"] is None
    assert card["scores"]["fundamental"] is None and card["scores"]["chip"] is None
    assert card["label"]["text"] == "資料不足"


# ═════════════════════════════════════════════════════════════════════════════
# 既有資料缺陷的修正：淨利、負債比
# ═════════════════════════════════════════════════════════════════════════════

def long_table(rows):
    return pd.DataFrame(rows, columns=["date", "type", "value"])


def test_quarter_label_and_pivot():
    assert quarter_label("2026-06-30") == "2026Q2" and quarter_label("2025-12-31") == "2025Q4"
    p = pivot_quarters(long_table([("2026-06-30", "Revenue", 100), ("2026-06-30", "EPS", 2.5), ("2026-03-31", "Revenue", 90)]))
    assert p == {"2026Q2": {"Revenue": 100.0, "EPS": 2.5}, "2026Q1": {"Revenue": 90.0}}
    assert pivot_quarters(pd.DataFrame()) == {}


class FakeFinMind:
    def __init__(self, fs=None, bs=None):
        self.fs, self.bs = fs, bs

    async def get_financial_statements(self, *a):
        return self.fs

    async def get_balance_sheet(self, *a):
        return self.bs


def crawler_with(fs=None, bs=None):
    c = FundamentalCrawler.__new__(FundamentalCrawler)
    c.finmind = FakeFinMind(fs, bs)
    return c


def test_net_margin_comes_from_income_after_taxes():
    fs = long_table([("2026-06-30", "Revenue", 1000), ("2026-06-30", "GrossProfit", 500), ("2026-06-30", "OperatingIncome", 300),
                     ("2026-06-30", "IncomeAfterTaxes", 250), ("2026-06-30", "EPS", 3.0)])
    out = asyncio.run(crawler_with(fs=fs).get_financial_statements("2330", "2026-01-01", "2026-12-31"))
    assert out["margins"][0]["net_margin"] == 25.0      # 以前永遠是 None（讀不存在的 NetIncome 欄位）
    assert out["margins"][0]["gross_margin"] == 50.0 and out["eps_quarterly"] == [{"quarter": "2026Q2", "eps": 3.0}]


def test_debt_ratio_comes_from_the_balance_sheet():
    bs = long_table([("2026-03-31", "Liabilities", 400), ("2026-03-31", "TotalAssets", 1000),
                     ("2026-06-30", "Liabilities", 580), ("2026-06-30", "TotalAssets", 1000),
                     ("2026-06-30", "Equity", 420)])
    rows = asyncio.run(crawler_with(bs=bs).get_debt_ratios("2330", "2026-01-01", "2026-12-31"))
    assert rows == [{"quarter": "2026Q1", "debt_ratio": 40.0}, {"quarter": "2026Q2", "debt_ratio": 58.0}]
    assert asyncio.run(crawler_with(bs=pd.DataFrame()).get_debt_ratios("2330", "a", "b")) == []


# ═════════════════════════════════════════════════════════════════════════════
# API：快取、額度、錯誤
# ═════════════════════════════════════════════════════════════════════════════

FAKE_CARD = {"version": sc.SCORECARD_VERSION, "applicable": True, "symbol": "2330", "dimensions": [], "meta": {"failed": []}}


@pytest.fixture()
def api(monkeypatch):
    """回傳 (client, state)：state 記錄 build 次數、被扣的額度與寫入的快取。"""
    import app.api.analysis as mod
    from app.api import analytics

    state = {"built": [], "consumed": [], "cache": {}, "sets": []}

    async def fake_consume(key, cost=1, category="rate_limit"):
        state["consumed"].append((key, cost))
        return 1, 600

    async def fake_get(key):
        return state["cache"].get(key)

    async def fake_set(key, data, category="analysis"):
        state["sets"].append((key, category))
        state["cache"][key] = data

    async def fake_build(symbol):
        state["built"].append(symbol)
        return state.get("result", dict(FAKE_CARD, symbol=symbol, meta={"failed": []}))

    monkeypatch.setattr("app.db.cache.consume_fixed_window", fake_consume)
    monkeypatch.setattr("app.db.cache.get_cache", fake_get)
    monkeypatch.setattr("app.db.cache.set_cache", fake_set)
    monkeypatch.setattr(analytics, "_get_client_ip", lambda request: "9.9.9.9")
    monkeypatch.setattr(mod.scorecard_core, "build_scorecard", fake_build)
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app), state


def test_scorecard_rejects_non_taiwan_symbols_and_garbage(api):
    client, state = api
    assert client.get("/api/v1/analysis/AAPL/scorecard").status_code == 400
    assert client.get("/api/v1/analysis/2330;DROP/scorecard").status_code in (400, 404)
    assert state["built"] == []


def test_scorecard_etf_is_not_applicable_and_costs_nothing(api):
    client, state = api
    r = client.get("/api/v1/analysis/0050/scorecard")
    assert r.status_code == 200 and r.json()["data"]["applicable"] is False and "ETF" in r.json()["data"]["reason"]
    assert state["built"] == [] and all("fetch" not in k for k, _ in state["consumed"])


def test_scorecard_miss_charges_fetch_quota_builds_and_caches(api):
    client, state = api
    r = client.get("/api/v1/analysis/2330.TW/scorecard")          # 也接受 .TW 尾碼
    assert r.status_code == 200 and r.json()["data"]["symbol"] == "2330"
    assert state["built"] == ["2330"]
    assert ("scorecard_fetch:9.9.9.9", sc.FETCH_COST) in state["consumed"]
    assert len(state["sets"]) == 1 and state["sets"][0][1] == "stock_scorecard"


def test_scorecard_cache_hit_does_not_build_or_charge_fetch_quota(api):
    client, state = api
    client.get("/api/v1/analysis/2330/scorecard")
    state["consumed"].clear()
    r = client.get("/api/v1/analysis/2330/scorecard")
    assert r.status_code == 200 and state["built"] == ["2330"]    # 第二次沒再 build
    assert state["consumed"] == [("scorecard_req:9.9.9.9", 1)]    # 只有很寬的請求數


def test_scorecard_degraded_result_is_not_cached(api):
    client, state = api
    state["result"] = dict(FAKE_CARD, meta={"failed": ["per", "fin"]})
    r = client.get("/api/v1/analysis/2317/scorecard")
    assert r.status_code == 200 and state["sets"] == []           # 殘缺結果不存 6 小時


def test_scorecard_errors_map_to_404_and_502_without_leaking_details(api, monkeypatch):
    client, state = api
    import app.api.analysis as mod

    async def not_found(symbol):
        raise ValueError("查無日線資料（代碼錯誤或尚未上市）")

    async def boom(symbol):
        raise RuntimeError("token=abc123 secret")

    monkeypatch.setattr(mod.scorecard_core, "build_scorecard", not_found)
    r = client.get("/api/v1/analysis/9999/scorecard")
    assert r.status_code == 404 and "查無日線資料" in r.json()["detail"]
    monkeypatch.setattr(mod.scorecard_core, "build_scorecard", boom)
    r = client.get("/api/v1/analysis/2454/scorecard")
    assert r.status_code == 502 and "abc123" not in r.text


def test_scorecard_over_quota_returns_429_with_retry_after(api, monkeypatch):
    client, state = api

    async def over(key, cost=1, category="rate_limit"):
        return (1, 600) if "_req:" in key else (10_000, 125)

    monkeypatch.setattr("app.db.cache.consume_fixed_window", over)
    r = client.get("/api/v1/analysis/2330/scorecard")
    assert r.status_code == 429 and r.headers["retry-after"] == "125" and state["built"] == []
