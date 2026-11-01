"""ETF 綜合比較的計算核心：用合成資料驗證每個數字都能手算驗證。

重點是 Gemini 版出錯的地方：分割造成的價格斷層、除息要不要還原、填息怎麼算、
急跌區間的高低點順序。不需要 FinMind、不需要 MongoDB。
"""

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analysis import etf_compare as core


def _bars(closes, start="2024-01-02", spread=0.0):
    """連續日曆日的合成日線（不跳週末，簡化手算）。"""
    d0 = date.fromisoformat(start)
    return [
        {"date": (d0 + timedelta(days=i)).isoformat(), "close": c,
         "max": c * (1 + spread), "min": c * (1 - spread), "open": c}
        for i, c in enumerate(closes)
    ]


# ── 清洗與分割 ──────────────────────────────────────────────────────────────

def test_clean_bars_drops_suspended_days_and_sorts():
    rows = [
        {"date": "2024-01-03", "close": 11, "max": 11, "min": 11, "open": 11},
        {"date": "2024-01-02", "close": 10, "max": 10, "min": 10, "open": 10},
        {"date": "2024-01-04", "close": 0, "max": 0, "min": 0, "open": 0},  # 停牌
    ]
    out = core.clean_bars(rows)
    assert [b["date"] for b in out] == ["2024-01-02", "2024-01-03"]


def test_detects_and_adjusts_one_for_four_split():
    # 0050 實際情況：188.65 → 47.57（1 拆 4，含當日漲跌）
    bars = core.clean_bars(_bars([180.0, 188.65, 47.57, 48.0]))
    splits = core.detect_splits(bars)
    assert splits == [{"date": "2024-01-04", "factor": 4.0}]
    adj = core.apply_splits(bars, splits)
    assert adj[1]["close"] == pytest.approx(188.65 / 4)
    assert adj[2]["close"] == pytest.approx(47.57)  # 分割後不動


def test_ordinary_limit_moves_are_not_splits():
    bars = core.clean_bars(_bars([100, 110, 99, 108.9]))  # 連續漲跌停
    assert core.detect_splits(bars) == []


def test_reverse_split_detected():
    bars = core.clean_bars(_bars([10.0, 10.2, 40.5, 41.0]))  # 4 併 1
    s = core.detect_splits(bars)
    assert len(s) == 1 and s[0]["factor"] == pytest.approx(0.25)


def test_dividend_amount_rescaled_for_split_after_it():
    splits = [{"date": "2025-06-10", "factor": 4.0}]
    rows = [{"date": "2025-01-20", "stock_and_cache_dividend": 2.0, "before_price": 160.0,
             "reference_price": 158.0, "after_price": 158.0}]
    d = core.parse_dividends(rows, splits)[0]
    assert d["amount"] == pytest.approx(0.5)
    assert d["before"] == pytest.approx(40.0)


# ── 含息還原 ────────────────────────────────────────────────────────────────

def test_total_return_series_reinvests_dividend_on_ex_date():
    # 100, 100, [除息日: 前收 100, 參考價 95], 95, 95  → 還原後應該全部是 95（沒賺沒賠）
    bars = core.clean_bars(_bars([100, 100, 95, 95, 95]))
    divs = [{"date": bars[2]["date"], "amount": 5, "before": 100, "ref": 95}]
    adj = core.total_return_series(bars, divs)
    assert adj == pytest.approx([95, 95, 95, 95, 95])


def test_total_return_with_two_dividends_chains_factors():
    bars = core.clean_bars(_bars([100, 90, 90, 81, 81]))
    divs = [
        {"date": bars[1]["date"], "amount": 10, "before": 100, "ref": 90},   # 係數 0.9
        {"date": bars[3]["date"], "amount": 9, "before": 90, "ref": 81},     # 係數 0.9
    ]
    adj = core.total_return_series(bars, divs)
    # 最後一天 81 不動；除息日之前依序乘上 0.9、0.81
    assert adj[-1] == pytest.approx(81)
    assert adj[0] == pytest.approx(100 * 0.9 * 0.9)
    assert adj[0] == pytest.approx(adj[-1])  # 等於 100 → 81 的含息報酬為 0


def test_total_return_ignores_garbage_dividend_factor():
    bars = core.clean_bars(_bars([100, 100, 100]))
    divs = [{"date": bars[1]["date"], "amount": 1, "before": 100, "ref": 500}]  # 參考價 > 前收，資料錯誤
    assert core.total_return_series(bars, divs) == pytest.approx([100, 100, 100])


# ── 指標 ────────────────────────────────────────────────────────────────────

def test_max_drawdown():
    assert core.max_drawdown([100, 120, 90, 110]) == pytest.approx(90 / 120 - 1)
    assert core.max_drawdown([1, 2, 3]) == 0.0


def test_metrics_short_history_flags_and_skips_sharpe():
    bars = core.clean_bars(_bars([100 + i * 0.1 for i in range(30)]))
    m = core.compute_metrics(bars, [b["close"] for b in bars])
    assert m["sharpe"] is None and m["mdd"] is None
    assert m["cagr_3y"] is None and m["return_1y"] is None


def test_metrics_enough_days_but_under_one_year_marks_short_history():
    closes = [100 * (1.001 ** i) for i in range(120)]
    bars = core.clean_bars(_bars(closes))
    m = core.compute_metrics(bars, closes)
    assert m["short_history"] is True
    assert m["mdd"] == 0.0
    assert m["return_1y"] is None  # 資料沒涵蓋滿一年，不能亂給數字
    assert m["ann_return"] > 0


def test_cagr_3y_from_three_years_of_data():
    n = 365 * 3 + 20
    closes = [100 * (1.0003 ** i) for i in range(n)]
    bars = core.clean_bars(_bars(closes))
    m = core.compute_metrics(bars, closes)
    expected = (closes[-1] / closes[-1 - int(365.25 * 3)]) ** (1 / 3) - 1
    assert m["cagr_3y"] == pytest.approx(expected, rel=0.02)


def test_sharpe_zero_vol_is_none_not_division_error():
    closes = [100.0] * 100
    bars = core.clean_bars(_bars(closes))
    m = core.compute_metrics(bars, closes)
    assert m["sharpe"] is None


# ── 配息與填息 ──────────────────────────────────────────────────────────────

def _div(day, amount, before, ref=None):
    return {"date": day, "amount": amount, "before": before, "ref": ref or before - amount}


def test_fill_success_and_days_counted_in_trading_days():
    # 除息日 2024-01-12 前收 10；除息當天 9.5、之後逐日回升，第 4 個交易日站回 10
    closes = [10] * 10 + [9.5, 9.7, 9.9, 10.0, 10.2] + [10.1] * 5
    bars = core.clean_bars(_bars(closes))
    ex = bars[10]["date"]
    f = core.fill_stats(bars, [_div(ex, 0.5, 10.0)])
    assert f["filled"] == 1 and f["failed"] == 0 and f["pending"] == 0
    assert f["events"][0]["days"] == 4
    assert f["success_rate"] == 1.0


def test_fill_pending_not_counted_as_failure():
    closes = [10] * 10 + [9.0] * 5  # 除息後才 5 天，還沒填息
    bars = core.clean_bars(_bars(closes))
    f = core.fill_stats(bars, [_div(bars[10]["date"], 1.0, 10.0)])
    assert f["pending"] == 1 and f["failed"] == 0
    assert f["success_rate"] is None  # 沒有結案事件，不給勝率


def test_fill_failed_after_window():
    closes = [10] * 10 + [9.0] * (core.FILL_WINDOW_DAYS + 5)
    bars = core.clean_bars(_bars(closes))
    f = core.fill_stats(bars, [_div(bars[10]["date"], 1.0, 10.0)])
    assert f["failed"] == 1 and f["success_rate"] == 0.0


def test_dividend_summary_ttm_yield_and_non_payer():
    closes = [50.0] * 400
    bars = core.clean_bars(_bars(closes, start="2024-01-02"))
    divs = [_div(bars[300]["date"], 1.0, 50.0), _div(bars[380]["date"], 1.0, 50.0)]
    s = core.dividend_summary(bars, divs)
    assert s["pays_dividend"] is True
    assert s["yield_ttm"] == pytest.approx(2.0 / 50.0)
    none = core.dividend_summary(bars, [])
    assert none["pays_dividend"] is False and none["yield_ttm"] is None


# ── 評分 ────────────────────────────────────────────────────────────────────

def test_defense_score_matches_gemini_formula_checkpoints():
    # 這三個點是對 Gemini 截圖逐檔驗證過的：-11.4% → 95、-26.8% → 55、-17.5% → 88
    for mdd, score in ((-0.114, 95.0), (-0.268, 55.0), (-0.175, 88.0)):
        s = core.radar_scores({"mdd": mdd, "cagr_3y": 0.1, "sharpe": 1.0},
                              {"yield_ttm": 0.04}, {"success_rate": 1.0, "avg_days": 5})
        assert s["defense"] == pytest.approx(score, abs=0.6)


def test_non_payer_gets_none_not_zero_and_total_ignores_missing_axes():
    s = core.radar_scores({"mdd": -0.10, "cagr_3y": 0.30, "sharpe": 1.4},
                          {"yield_ttm": None}, {"success_rate": None, "avg_days": None})
    assert s["yield"] is None and s["fill"] is None
    assert s["return"] == 100.0 and s["sharpe"] == 100.0
    assert s["total"] == pytest.approx((100 + 95 + 100) / 3, abs=0.1)


def test_return_score_falls_back_to_annualized_when_under_3y():
    s = core.radar_scores({"mdd": -0.1, "cagr_3y": None, "ann_return": 0.15, "sharpe": 0.7},
                          {"yield_ttm": 0.05}, {"success_rate": None, "avg_days": None})
    assert s["return"] == pytest.approx(50.0)
    assert s["return_basis"] == "ann_return"


# ── 急跌與反彈 ──────────────────────────────────────────────────────────────

def test_event_window_orders_high_before_low_and_finds_rebound():
    # 先漲到高點 120（第 5 天）、跌到低點 90（第 12 天）、再反彈到 110
    closes = [100, 105, 110, 115, 118, 120, 118, 112, 108, 100, 95, 92, 90, 95, 100, 105, 110, 108]
    bars = core.clean_bars(_bars(closes, spread=0.0))
    ev = core.event_window(bars, [], bars[0]["date"], bars[12]["date"], bars[-1]["date"])
    assert ev["high"] == 120 and ev["low"] == 90
    assert ev["high_date"] < ev["low_date"]
    assert ev["drawdown"] == pytest.approx(90 / 120 - 1)
    assert ev["rebound_high"] == 110
    assert ev["rebound_pct"] == pytest.approx(110 / 90 - 1)


def test_event_window_low_must_come_after_high():
    # 區間內最低價在最高價「之前」→ 不能拿它當跌幅
    closes = [50, 60, 70, 100, 99, 98]
    bars = core.clean_bars(_bars(closes))
    ev = core.event_window(bars, [], bars[0]["date"], bars[-1]["date"])
    assert ev["high"] == 100
    assert ev["low"] == 98
    assert ev["drawdown"] == pytest.approx(98 / 100 - 1)


def test_event_window_counts_dividends_and_partial_listing():
    bars = core.clean_bars(_bars([100, 98, 96, 94], start="2024-03-01"))
    ev = core.event_window(bars, [{"date": "2024-03-03", "amount": 0.7}], "2024-02-01", "2024-03-04")
    assert ev["dividends_in_window"] == pytest.approx(0.7)
    assert ev["partial"] is True  # 上市日比區間起點還晚


def test_find_drawdown_episode_detects_largest_and_ignores_small_dips():
    closes = [100] * 5 + [110, 120, 130, 125, 100, 95, 105, 115] + [116] * 20
    bars = core.clean_bars(_bars(closes))
    ep = core.find_drawdown_episode(bars, [b["close"] for b in bars])
    assert ep["start"] == bars[7]["date"]  # 130 是高點
    assert ep["end"] == bars[10]["date"]   # 95 是低點
    assert ep["drop"] == pytest.approx(95 / 130 - 1)

    calm = core.clean_bars(_bars([100 + (i % 3) for i in range(60)]))
    assert core.find_drawdown_episode(calm, [b["close"] for b in calm]) is None


# ── 整合：單檔 bundle ───────────────────────────────────────────────────────

def test_build_symbol_bundle_end_to_end_with_split_and_dividend():
    n = 400
    closes = [100 + i * 0.05 for i in range(n)]
    rows = _bars(closes, start="2023-01-02")
    # 在第 200 天發生 1 拆 4：之後的價格都除以 4
    for i in range(200, n):
        for k in ("close", "max", "min", "open"):
            rows[i][k] /= 4
    ex_day = rows[250]["date"]
    div_rows = [{"date": ex_day, "stock_and_cache_dividend": 0.25, "before_price": rows[249]["close"],
                 "reference_price": rows[249]["close"] - 0.25}]
    b = core.build_symbol_bundle(rows, div_rows)
    assert b["splits"] and b["splits"][0]["factor"] == 4.0
    assert b["metrics"]["last_close"] == pytest.approx(closes[-1] / 4)
    assert b["dividends"]["pays_dividend"] is True
    assert b["series"]["adj"][0] > 0
    # 分割沒處理的話 MDD 會是 -75%；處理後應該是溫和的小回撤
    assert b["metrics"]["mdd"] > -0.05


def test_build_symbol_bundle_none_when_no_usable_bars():
    assert core.build_symbol_bundle([], []) is None
    assert core.build_symbol_bundle([{"date": "2024-01-02", "close": 0}], []) is None


# ── 分類 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sym,name,cat", [
    ("00981A", "主動統一台股增長", "active"),
    ("0056", "元大高股息", "dividend"),
    ("00878", "國泰永續高股息", "dividend"),
    ("0050", "元大台灣50", "market"),
    ("006208", "富邦台50", "market"),
    ("00679B", "元大美債20年", "other"),
])
def test_classify_etf(sym, name, cat):
    assert core.classify_etf(sym, name) == cat


# ── API 層：輸入驗證（不碰 FinMind／Mongo）────────────────────────────────

@pytest.fixture()
def client():
    from app.api.etf_compare import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.parametrize("q", ["", "   ", ",,,"])
def test_compare_rejects_empty(client, q):
    r = client.get("/api/v1/etf-compare/compare", params={"symbols": q})
    assert r.status_code == 400


def test_compare_rejects_bad_symbol_and_too_many(client):
    assert client.get("/api/v1/etf-compare/compare", params={"symbols": "0050;DROP"}).status_code == 400
    many = ",".join(f"00{i:03d}" for i in range(11))
    assert client.get("/api/v1/etf-compare/compare", params={"symbols": many}).status_code == 400


def test_compare_rejects_bad_event_dates(client):
    base = {"symbols": "0050"}
    assert client.get("/api/v1/etf-compare/compare", params={**base, "event_start": "2025-13-01", "event_end": "2025-12-01"}).status_code == 400
    assert client.get("/api/v1/etf-compare/compare", params={**base, "event_start": "2025-01-01"}).status_code == 400
    assert client.get("/api/v1/etf-compare/compare", params={**base, "event_start": "2025-05-01", "event_end": "2025-01-01"}).status_code == 400
    assert client.get("/api/v1/etf-compare/compare", params={**base, "event_start": "2023-01-01", "event_end": "2025-01-01"}).status_code == 400
