"""配息體檢（analysis/etf_dividend_health.py）：用合成資料驗證每個數字都能手算。

不需要 FinMind、不需要 MongoDB。門檻值直接引用模組常數，改門檻時測試會一起指出要看哪裡。
"""

import json
from datetime import date, timedelta

import pytest

from app.analysis import etf_compare as core
from app.analysis import etf_dividend_health as h

START = date(2023, 1, 2)


def _bars(closes, start=START):
    return [{"date": (start + timedelta(days=i)).isoformat(), "close": float(c)} for i, c in enumerate(closes)]


def _divs(bars, idxs, amounts, drop=True):
    """在 bars 的第 idx 根當除息日；before＝前一日收盤、ref＝before − 金額（填息判斷與還原用）。"""
    out = []
    for i, a in zip(idxs, amounts):
        before = bars[i - 1]["close"]
        out.append({"date": bars[i]["date"], "amount": float(a), "before": before, "ref": before - a if drop else before})
    return out


def _adj(bars, divs):
    return core.total_return_series(bars, divs)


# ── 配息頻率 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("gap,expected", [(30, 12), (91, 4), (182, 2), (365, 1)])
def test_infer_frequency_from_median_gap(gap, expected):
    ds = [{"date": (START + timedelta(days=gap * i)).isoformat(), "amount": 1.0} for i in range(6)]
    assert h.infer_frequency(ds) == expected


def test_infer_frequency_needs_three_events():
    ds = [{"date": "2024-01-10", "amount": 1.0}, {"date": "2024-04-10", "amount": 1.0}]
    assert h.infer_frequency(ds) is None


# ── 資料不足 ────────────────────────────────────────────────────────────────

def test_no_dividends_is_unknown_with_reason():
    out = h.dividend_health(_bars([100] * 400), [])
    assert out["enough"] is False and out["verdict"] == "unknown" and "沒有除息" in out["reason"]


def test_fewer_than_min_payouts_is_unknown_but_keeps_payout_list():
    bars = _bars([100] * 400)
    divs = _divs(bars, [200, 300, 390], [1.0, 1.0, 1.0])
    out = h.dividend_health(bars, divs)
    assert out["enough"] is False and str(h.MIN_PAYOUTS) in out["reason"]
    assert [p["amount"] for p in out["payouts"]] == [1.0, 1.0, 1.0]


def test_stopped_paying_in_last_12_months_is_unknown_with_clear_reason():
    bars = _bars([100] * 800)
    divs = _divs(bars, [70, 160, 250, 340, 430], [1.0] * 5)  # 最後一次除息在 369 天前，已超出近 12 個月
    out = h.dividend_health(bars, divs)
    assert out["enough"] is False and "近 12 個月沒有除息" in out["reason"]


# ── 殖利率膨脹 ──────────────────────────────────────────────────────────────

def _price_drop_case():
    # 600 根日線：前 500 根 100 元，最後 100 根 70 元；近 365 天（第 235～599 根）= 265 根 100 + 100 根 70
    closes = [100] * 500 + [70] * 100
    bars = _bars(closes)
    divs = _divs(bars, [156, 247, 338, 429, 520], [1.0] * 5)
    return bars, divs


def test_yield_inflation_when_price_dropped():
    bars, divs = _price_drop_case()
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    avg = (265 * 100 + 100 * 70) / 365
    assert out["avg_close_ttm"] == pytest.approx(avg, abs=1e-3)
    assert out["ttm_amount"] == pytest.approx(4.0)  # 247/338/429/520 四次在近 365 天內
    assert out["yield_now"] == pytest.approx(4.0 / 70, abs=1e-5)
    assert out["yield_norm"] == pytest.approx(4.0 / avg, abs=1e-5)
    assert out["inflation"] == pytest.approx(avg / 70, abs=1e-3)  # ≈ 1.311
    chk = next(c for c in out["checks"] if c["key"] == "inflation")
    assert chk["level"] == "bad"  # 1.311 > 1.30


def test_no_inflation_when_price_is_flat_or_higher():
    bars = _bars([100] * 300 + [120] * 300)
    divs = _divs(bars, [156, 247, 338, 429, 520], [1.0] * 5)
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    chk = next(c for c in out["checks"] if c["key"] == "inflation")
    assert out["inflation"] < 1.0 and chk["level"] == "good" and "沒有跌價撐高" in chk["text"]


# ── 配息穩定度 ──────────────────────────────────────────────────────────────

IDX8 = [100 + 91 * k for k in range(8)]  # 8 次季配：100,191,…,737；第 k 次與第 k-4 次相隔 364 天＝去年同期


def _stability(amounts, idxs=None, n_bars=800):
    bars = _bars([100] * n_bars)
    divs = _divs(bars, idxs or IDX8, amounts)
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    return out, next(c for c in out["checks"] if c["key"] == "stability")


def test_stability_good_when_no_payout_was_cut():
    out, chk = _stability([1.0] * 8)
    assert chk["level"] == "good" and out["stability"]["cuts"] == 0 and out["stability"]["worst_ratio"] == 1.0
    assert "都沒有比去年同期" in chk["text"] and "減少" in chk["text"]


def test_stability_text_reports_worst_ratio_when_some_payout_dipped_but_not_enough_to_cut():
    out, chk = _stability([1, 1, 1, 1, 1, 1, 0.9, 1])  # 最差 90%，未達縮水門檻
    assert chk["level"] == "good" and "最差 90%" in chk["text"]


def test_stability_one_cut_vs_same_period_last_year_is_warn():
    out, chk = _stability([1, 1, 1, 1, 1, 1, 0.7, 1])  # 第 7 次只有去年同期的 70%
    assert chk["level"] == "warn" and out["stability"]["cuts"] == 1 and out["stability"]["compared"] == 4
    assert out["stability"]["worst_ratio"] == pytest.approx(0.7)


def test_stability_two_or_more_cuts_is_bad():
    out, chk = _stability([1, 1, 1, 1, 0.7, 0.7, 0.7, 1.0])
    assert chk["level"] == "bad" and out["stability"]["cuts"] == 3


def test_stability_exactly_at_cut_ratio_is_not_a_cut():
    out, chk = _stability([1, 1, 1, 1, 1, 1, 1, 0.8])  # 正好 80%：「少超過 20%」才算縮水
    assert out["stability"]["cuts"] == 0 and chk["level"] == "good"


def test_rising_payouts_are_not_flagged_as_unstable():
    # 越配越多（例如 00929 這類配息逐步調高）：金額起伏大，但沒有縮水，不能判不穩
    out, chk = _stability([0.1, 0.1, 0.1, 0.1, 0.4, 0.4, 0.4, 0.4])
    assert out["stability"]["cv"] > 0.5 and chk["level"] == "good"


def test_seasonal_high_low_pattern_is_not_flagged_as_unstable():
    # 半年配／季節性：高低每年都一樣（例如 0050），跟去年同期比沒縮水
    out, chk = _stability([1.0, 0.4, 1.0, 0.4, 1.0, 0.4, 1.0, 0.4])
    assert out["stability"]["cv"] > 0.4 and chk["level"] == "good"


def test_stability_falls_back_to_previous_payout_without_a_year_ago_match():
    bars = _bars([100] * 400)
    divs = _divs(bars, [100, 191, 282, 373], [1.0, 1.0, 1.0, 0.5])
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    # 第一次沒有前期可比（略過）；其餘跟前一次比：1.0、1.0、0.5
    assert out["stability"]["compared"] == 3 and out["stability"]["cuts"] == 1


# ── 近期趨勢（季節性：先比去年同期）────────────────────────────────────────

def test_trend_uses_same_period_last_year_so_seasonal_dip_is_not_flagged():
    bars = _bars([100] * 700)
    # 第 4 季本來就少：去年同期 1.0、今年同期 1.0（即使比前一季 1.4 少很多也不算縮水）
    divs = _divs(bars, [65, 156, 247, 338, 429, 520, 611, 702 - 3], [1.0, 1.2, 1.4, 1.0, 1.0, 1.2, 1.4, 1.0])
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    assert out["trend"]["basis"] == "yoy"
    assert out["trend"]["ratio"] == pytest.approx(1.0)
    assert next(c for c in out["checks"] if c["key"] == "trend")["level"] == "good"


def test_trend_flags_real_cut_vs_same_period_last_year():
    bars = _bars([100] * 700)
    divs = _divs(bars, [65, 156, 247, 338, 429, 520, 611, 702 - 3], [1.0, 1.2, 1.4, 1.0, 1.0, 1.2, 1.4, 0.6])
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    assert out["trend"]["basis"] == "yoy" and out["trend"]["ratio"] == pytest.approx(0.6)
    assert next(c for c in out["checks"] if c["key"] == "trend")["level"] == "bad"  # 0.6 < 0.75


def test_trend_surge_is_not_a_warning_but_points_to_the_distribution_source():
    bars = _bars([100] * 700)
    divs = _divs(bars, [65, 156, 247, 338, 429, 520, 611, 702 - 3], [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.8])
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    chk = next(c for c in out["checks"] if c["key"] == "trend")
    assert chk["level"] == "good" and "增幅很大" in chk["text"] and "配息來源" in chk["text"]


def test_trend_falls_back_to_previous_average_when_no_year_ago_event():
    bars = _bars([100] * 400)
    divs = _divs(bars, [100, 191, 282, 373], [1.0, 1.0, 1.0, 0.5])  # 沒有一年前的事件
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    assert out["trend"]["basis"] == "prev_avg" and out["trend"]["ratio"] == pytest.approx(0.5)


# ── 情境殖利率 ──────────────────────────────────────────────────────────────
# 保守＝近 12 月與前一個 12 月配息總額取低者；中性＝近 12 月；最近一次年化＝最近一次 × 年配次數。
# 都以現價換算。1,100 根日線、11 次季配（idx 100,191,…,1010），最後一根是 idx 1099：
# 近 12 月 = idx 737/828/919/1010，前一個 12 月 = idx 373/464/555/646。

IDX11 = [100 + 91 * k for k in range(11)]


def _scen(amounts, n_bars=1100, idxs=None):
    bars = _bars([50] * n_bars)
    divs = _divs(bars, idxs or IDX11, amounts)
    return h.dividend_health(bars, divs, adj=_adj(bars, divs))["scenarios"]


def test_scenarios_conservative_uses_lower_of_this_year_and_prior_year():
    s = _scen([1, 1, 1] + [1.0] * 4 + [1.2] * 4)  # 前一年 4.0、近 12 月 4.8
    assert s["freq"] == 4 and s["freq_label"] == "季配"
    assert s["conservative"] == pytest.approx(4.0 / 50)
    assert s["neutral"] == pytest.approx(4.8 / 50)
    assert s["last_annualized"] == pytest.approx(1.2 * 4 / 50)


def test_scenarios_conservative_is_this_year_when_it_was_lower():
    s = _scen([1, 1, 1] + [1.5] * 4 + [1.2] * 4)  # 前一年 6.0 > 近 12 月 4.8
    assert s["conservative"] == pytest.approx(4.8 / 50) and s["neutral"] == pytest.approx(4.8 / 50)


def test_scenarios_conservative_is_none_without_a_full_prior_year():
    # 只有 500 根日線：前一個 12 個月 ETF 還不存在，總額不可比，不硬推算保守情境
    s = _scen([1.0] * 4, n_bars=500, idxs=[150, 241, 332, 423])
    assert s["conservative"] is None
    assert s["neutral"] == pytest.approx(4.0 / 50) and s["last_annualized"] == pytest.approx(4.0 / 50)


def test_monthly_payer_scenarios_do_not_collapse_to_one_number():
    # 月配、最近幾個月配息調高（最近 4 次都是 0.38）：最近一次年化 ≠ 近 12 月 ≠ 保守，三個數字要拉開
    n = 1100
    bars = _bars([26] * n)
    idxs = [n - 1 - 30 * k for k in range(18)][::-1]
    amounts = [0.1] * 12 + [0.13, 0.26, 0.38, 0.38, 0.38, 0.38]
    divs = _divs(bars, idxs, amounts)
    s = h.dividend_health(bars, divs, adj=_adj(bars, divs))["scenarios"]
    assert s["freq"] == 12
    assert s["conservative"] < s["neutral"] < s["last_annualized"]


# ── 吃本金 ──────────────────────────────────────────────────────────────────

def _falling_with_dividends():
    n = 1100  # 約 3 年
    closes = [100 - 30 * i / (n - 1) for i in range(n)]
    bars = _bars(closes)
    idxs = list(range(100, n, 91))
    divs = _divs(bars, idxs, [1.25] * len(idxs))
    return bars, divs


def test_principal_erosion_when_price_loss_exceeds_dividends():
    bars, divs = _falling_with_dividends()
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    p = out["principal"]
    assert p["price_return"] == pytest.approx(-0.30, abs=0.01)
    assert p["total_return"] > p["price_return"]
    assert p["erosion"] == pytest.approx(0.30 / p["dist_contribution"], abs=0.02)
    chk = next(c for c in out["checks"] if c["key"] == "principal")
    assert chk["level"] == "bad" and "價格下跌吃掉" in chk["text"]


def test_principal_good_when_price_not_falling():
    n = 1100
    bars = _bars([100 + 10 * i / (n - 1) for i in range(n)])
    idxs = list(range(100, n, 91))
    divs = _divs(bars, idxs, [1.0] * len(idxs))
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    chk = next(c for c in out["checks"] if c["key"] == "principal")
    assert chk["level"] == "good" and out["principal"]["erosion"] == 0.0


def test_low_fill_rate_bumps_principal_check_one_level():
    n = 1100
    bars = _bars([100 + 10 * i / (n - 1) for i in range(n)])
    idxs = list(range(100, n, 91))
    divs = _divs(bars, idxs, [1.0] * len(idxs))
    out = h.dividend_health(bars, divs, fill={"success_rate": 0.2}, adj=_adj(bars, divs))
    chk = next(c for c in out["checks"] if c["key"] == "principal")
    assert chk["level"] == "warn" and "填不回來" in chk["text"]


def test_principal_is_na_for_short_history():
    bars = _bars([100] * 200)
    divs = _divs(bars, [20, 60, 100, 140, 180], [1.0] * 5)
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    assert next(c for c in out["checks"] if c["key"] == "principal")["level"] == "na"
    assert out["principal"] is None


# ── 總評與輸出 ──────────────────────────────────────────────────────────────

def test_steady_verdict_for_flat_price_equal_dividends():
    bars = _bars([100] * 1100)
    idxs = list(range(100, 1100, 91))
    divs = _divs(bars, idxs, [1.0] * len(idxs))
    out = h.dividend_health(bars, divs, fill={"success_rate": 1.0}, adj=_adj(bars, divs))
    assert out["enough"] is True and out["verdict"] == "steady" and out["verdict_label"] == "穩定"
    assert all(c["level"] == "good" for c in out["checks"])


def test_any_bad_check_makes_verdict_weak():
    bars, divs = _price_drop_case()  # 膨脹 bad
    out = h.dividend_health(bars, divs, adj=_adj(bars, divs))
    assert out["verdict"] == "weak"


@pytest.mark.parametrize("levels,expected", [
    ([], "unknown"),
    (["na", "na"], "unknown"),
    (["good", "good", "good", "na"], "steady"),
    (["good", "warn", "good", "good"], "watch"),
    (["warn", "warn", "good", "good"], "watch"),
    (["warn", "warn", "warn", "good"], "weak"),
    (["good", "good", "bad", "good"], "weak"),
])
def test_verdict_rules(levels, expected):
    assert h.verdict_from_levels(levels) == expected


def test_output_is_json_serializable_and_has_four_checks():
    bars, divs = _price_drop_case()
    out = h.dividend_health(bars, divs, fill={"success_rate": 0.9}, adj=_adj(bars, divs))
    json.dumps(out, ensure_ascii=False)
    assert [c["key"] for c in out["checks"]] == ["inflation", "stability", "trend", "principal"]


def test_bundle_carries_health_from_finmind_shaped_rows():
    closes = [100.0] * 700
    rows = [{"date": (START + timedelta(days=i)).isoformat(), "open": c, "max": c, "min": c, "close": c,
             "Trading_Volume": 1000} for i, c in enumerate(closes)]
    div_rows = [{"date": rows[i]["date"], "stock_and_cache_dividend": 1.0, "before_price": 100.0,
                 "reference_price": 99.0} for i in (65, 156, 247, 338, 429, 520, 611)]
    b = core.build_symbol_bundle(rows, div_rows)
    assert b["health"]["enough"] is True and b["health"]["freq_label"] == "季配"
    json.dumps(b["health"], ensure_ascii=False)
