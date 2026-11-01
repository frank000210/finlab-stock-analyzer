"""ETF／個股綜合比較（etf-compare）的計算核心。

這個模組只有「純函式」：輸入是 FinMind 的日線與除息資料（list[dict]），輸出是
圖表需要的所有數字。刻意不碰網路與資料庫，才能用固定資料做單元測試，也才能保證
「頁面上的每個數字都是算出來的，而不是手寫的」。

背景：使用者用 Gemini 做過一版同類頁面，數字是 Gemini 寫死在程式裡的，對 FinMind
實際日線核對後有多處錯誤（南亞科把 8 月高點當成 7 月高點、星期日當交易日…）。
這裡的設計原則是反過來：一切從原始日線與除息紀錄推導。

資料處理三步（順序不能換）：
1. 清掉無效列（收盤 <= 0）。
2. 偵測「股票分割／反向分割」：FinMind 的原始價格沒有處理分割（例如 0050 在
   2025-06 1 拆 4，收盤價 188.65 → 47.57），單日漲跌超過 ±40% 在台股（漲跌幅
   10%）只可能是分割，用整數倍率把分割前的價格還原到現在的尺度。
3. 含息還原：用 TaiwanStockDividendResult 的「除息前一日收盤 → 除息參考價」比例，
   把除息日以前的價格往下調，得到還原價（等於股息在除息日再投入）。
   價位（高低點、殖利率分母）用「只做分割調整、不含息還原」的價格，因為那才是使用者
   在看盤軟體上看到的價格。
"""

from __future__ import annotations

import math
import statistics
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta
from typing import Any, Optional

# ── 評分與統計參數（全部在這裡，頁面上的「計算方式」說明要與此一致）────────────
RISK_FREE_RATE = 0.015  # 夏普值的無風險利率（年）
TRADING_DAYS = 252
MIN_STATS_DAYS = 60  # 少於這個交易日數，不算波動／夏普／MDD
SPLIT_JUMP = 0.40  # 單日漲跌幅超過 ±40% 視為分割（台股漲跌幅限制 10%）
FILL_WINDOW_DAYS = 60  # 填息觀察期（交易日）：超過仍未填息算失敗；未滿則算「未結案」
FILL_LOOKBACK_YEARS = 3  # 填息統計只看最近幾年的除息

# 五維分數的換算（皆夾在 0–100）
RETURN_FULL_SCORE_AT = 0.30  # 年化報酬 30% 以上拿滿分
DEFENSE_BASE_MDD = 14.0  # 抗跌：|MDD| 14% 以內拿高分（沿用 Gemini 版公式，截圖驗證過）
DEFENSE_SLOPE = 3.5
DEFENSE_MIN, DEFENSE_MAX = 30.0, 95.0
SHARPE_FULL_SCORE_AT = 1.4
YIELD_FULL_SCORE_AT = 0.10  # 現金殖利率 10% 拿滿分


def _d(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ═════════════════════════════════════════════════════════════════════════════
# 1. 價格整理：清洗、分割調整、含息還原
# ═════════════════════════════════════════════════════════════════════════════

def clean_bars(rows: list[dict]) -> list[dict]:
    """FinMind TaiwanStockPrice 的列 → [{date, open, high, low, close}]，依日期排序。

    收盤價 <= 0（停牌日）的列直接丟掉，否則會產生 -100% / 無限大的報酬。
    """
    out = []
    for r in rows or []:
        try:
            close = float(r.get("close"))
        except (TypeError, ValueError):
            continue
        if not close or close <= 0:
            continue
        high = float(r.get("max", r.get("high", close)) or close)
        low = float(r.get("min", r.get("low", close)) or close)
        opn = float(r.get("open", close) or close)
        out.append({"date": str(r["date"])[:10], "open": opn, "high": high, "low": low, "close": close})
    out.sort(key=lambda b: b["date"])
    return out


def detect_splits(bars: list[dict]) -> list[dict]:
    """找出分割事件：[{date, factor}]，factor>1 為分割（1 拆 N），<1 為反向分割。

    單日 close 變動超過 ±SPLIT_JUMP 才視為分割；倍率取最接近的 0.5 的倍數，
    因為真實的當日漲跌（最多 ±10%）會讓比值偏離整數一點點（188.65/47.57 = 3.97 → 4）。
    """
    events = []
    for prev, cur in zip(bars, bars[1:]):
        ratio = prev["close"] / cur["close"]
        if ratio > 1 / (1 - SPLIT_JUMP) or ratio < 1 - SPLIT_JUMP:
            factor = round(ratio * 2) / 2 if ratio >= 1.5 else round(ratio * 4) / 4
            if factor > 0 and abs(factor - 1) > 1e-9:
                events.append({"date": cur["date"], "factor": factor})
    return events


def apply_splits(bars: list[dict], splits: list[dict]) -> list[dict]:
    """把分割日之前的價格除以倍率，讓整段價格是現在的尺度。"""
    if not splits:
        return [dict(b) for b in bars]
    out = []
    for b in bars:
        f = 1.0
        for s in splits:
            if b["date"] < s["date"]:
                f *= s["factor"]
        out.append({
            "date": b["date"],
            "open": b["open"] / f, "high": b["high"] / f, "low": b["low"] / f, "close": b["close"] / f,
        })
    return out


def split_factor_after(day: str, splits: list[dict]) -> float:
    """在 day「之後」才發生的分割的累積倍率（用來把舊的每股金額換成現在的尺度）。"""
    f = 1.0
    for s in splits:
        if s["date"] > day:
            f *= s["factor"]
    return f


def parse_dividends(rows: list[dict], splits: list[dict]) -> list[dict]:
    """TaiwanStockDividendResult → [{date(除息日), amount(每股現金股利, 現在尺度), before, ref}]。

    只取「息」與「權息」且有現金金額的列。before 是除息前一日收盤、ref 是除息參考價，
    兩者都換算成現在的價格尺度，才能和已做分割調整的日線比較（填息判斷用）。
    """
    out = []
    for r in rows or []:
        try:
            amount = float(r.get("stock_and_cache_dividend") or 0)
            before = float(r.get("before_price") or 0)
            ref = float(r.get("reference_price") or r.get("after_price") or 0)
        except (TypeError, ValueError):
            continue
        day = str(r.get("date", ""))[:10]
        if not day or amount <= 0 or before <= 0 or ref <= 0:
            continue
        f = split_factor_after(day, splits)
        out.append({"date": day, "amount": amount / f, "before": before / f, "ref": ref / f,
                    "raw_before": before, "raw_ref": ref})
    out.sort(key=lambda d: d["date"])
    return out


def total_return_series(bars: list[dict], dividends: list[dict]) -> list[float]:
    """含息還原收盤價序列（與 bars 等長）。

    除息日的還原係數 = 除息參考價 / 除息前一日收盤（< 1）；除息日「之前」的價格都乘上它，
    等於假設股息在除息日以參考價再投入。多次除息的係數連乘。
    """
    n = len(bars)
    adj = [b["close"] for b in bars]
    if not dividends or n == 0:
        return adj
    dates = [b["date"] for b in bars]
    cum = 1.0
    # 從最近的除息往回處理：越早的價格，要乘上它「之後」所有除息的係數
    factors = {}
    for dv in sorted(dividends, key=lambda d: d["date"], reverse=True):
        idx = bisect_left(dates, dv["date"])  # 除息日（或之後第一個交易日）的位置
        if idx <= 0 or idx > n:
            continue
        f = dv["ref"] / dv["before"] if dv["before"] else 1.0
        if not (0 < f <= 1.2):  # 排除異常（資料錯誤）
            continue
        factors[idx] = factors.get(idx, 1.0) * f
    multiplier = [1.0] * n
    cum = 1.0
    for i in range(n - 1, -1, -1):
        multiplier[i] = cum
        # i 這一天本身若是除息日，則 i 之前的價格要多乘這次的係數
        if i in factors:
            cum *= factors[i]
    return [adj[i] * multiplier[i] for i in range(n)]


# ═════════════════════════════════════════════════════════════════════════════
# 2. 績效指標
# ═════════════════════════════════════════════════════════════════════════════

def _daily_returns(values: list[float]) -> list[float]:
    return [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]


def max_drawdown(values: list[float]) -> Optional[float]:
    """最大回撤（負的小數，例如 -0.164 = -16.4%）。"""
    if len(values) < 2:
        return None
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return worst


def _idx_on_or_before(dates: list[str], day: str) -> int:
    """<= day 的最後一個索引；沒有則 -1。"""
    return bisect_right(dates, day) - 1


def compute_metrics(bars: list[dict], adj: list[float], asof: Optional[str] = None) -> dict:
    """報酬、CAGR、波動、夏普、MDD。資料不足的欄位回 None（頁面顯示「資料不足」）。"""
    if not bars:
        return {}
    dates = [b["date"] for b in bars]
    asof = asof or dates[-1]
    last_i = _idx_on_or_before(dates, asof)
    last = _d(dates[last_i])
    out: dict[str, Any] = {
        "listing_date": dates[0],
        "history_days": last_i + 1,
        "last_close": bars[last_i]["close"],
        "last_date": dates[last_i],
    }

    def ret_since(years: float) -> Optional[float]:
        start_day = (last - timedelta(days=int(365.25 * years))).isoformat()
        # 需要資料真的涵蓋到該起點（容許 7 天誤差，假日/停牌）
        if _d(dates[0]) > _d(start_day) + timedelta(days=7):
            return None
        i = max(_idx_on_or_before(dates, start_day), 0)
        base = adj[i]
        return adj[last_i] / base - 1 if base > 0 else None

    r1 = ret_since(1)
    r3 = ret_since(3)
    out["return_1y"] = r1
    out["cagr_3y"] = (1 + r3) ** (1 / 3) - 1 if r3 is not None else None

    # 統計窗口：最近 1 年，上市不滿 1 年就用上市以來（至少 MIN_STATS_DAYS 個交易日）
    start_day = (last - timedelta(days=365)).isoformat()
    s_i = max(_idx_on_or_before(dates, start_day), 0)
    win = adj[s_i:last_i + 1]
    out["window_days"] = len(win)
    out["short_history"] = _d(dates[0]) > _d(start_day) + timedelta(days=7)
    if len(win) < MIN_STATS_DAYS:
        out.update({"ann_return": None, "ann_vol": None, "sharpe": None, "mdd": None})
        return out

    rets = _daily_returns(win)
    mean_d = statistics.fmean(rets)
    sd_d = statistics.stdev(rets) if len(rets) > 1 else 0.0
    # 年化報酬用視窗首尾的實際複利換算（滿一年時就等於近 1 年報酬）；
    # 不用「日均報酬 ×252」——波動大時它會系統性高估。夏普仍採標準的算術年化。
    span_days = max((_d(dates[last_i]) - _d(dates[s_i])).days, 1)
    ann_ret = (win[-1] / win[0]) ** (365 / span_days) - 1
    ann_vol = sd_d * math.sqrt(TRADING_DAYS)
    out["ann_return"] = ann_ret
    out["ann_vol"] = ann_vol
    out["sharpe"] = (mean_d * TRADING_DAYS - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else None
    out["mdd"] = max_drawdown(win)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 3. 配息與填息
# ═════════════════════════════════════════════════════════════════════════════

def dividend_summary(bars: list[dict], dividends: list[dict], years: int = 3) -> dict:
    """歷年配息（最近 years 個曆年）、近 12 個月殖利率、是否配息。"""
    if not bars:
        return {"pays_dividend": False, "yield_ttm": None, "by_year": [], "events": []}
    last_close = bars[-1]["close"]
    last = _d(bars[-1]["date"])
    ttm_start = (last - timedelta(days=365)).isoformat()
    ttm_amt = sum(d["amount"] for d in dividends if d["date"] > ttm_start)
    pays = bool(dividends)
    by_year = []
    for y in range(last.year - years + 1, last.year + 1):
        ys = f"{y}-01-01"
        ye = f"{y}-12-31"
        amt = sum(d["amount"] for d in dividends if ys <= d["date"] <= ye)
        # 殖利率分母：該年最後一個交易日收盤（進行中的年度用最新收盤）
        in_year = [b for b in bars if b["date"] <= ye]
        price = in_year[-1]["close"] if in_year and in_year[-1]["date"] >= ys else None
        by_year.append({
            "year": y,
            "amount": round(amt, 4),
            "yield": (amt / price) if (price and amt > 0) else (0.0 if price else None),
            "count": sum(1 for d in dividends if ys <= d["date"] <= ye),
            "partial": y == last.year,
        })
    events = [{"date": d["date"], "amount": round(d["amount"], 4)} for d in dividends
              if d["date"] >= f"{last.year - years + 1}-01-01"]
    return {
        "pays_dividend": pays,
        "yield_ttm": (ttm_amt / last_close) if (pays and last_close) else None,
        "ttm_amount": round(ttm_amt, 4),
        "by_year": by_year,
        "events": events,
    }


def fill_stats(bars: list[dict], dividends: list[dict], asof: Optional[str] = None) -> dict:
    """填息統計：最近 FILL_LOOKBACK_YEARS 年每次除息，從除息日起幾個交易日內收盤站回除息前價。

    - 填息天數：除息日當天收盤就站回 = 1，隔天 = 2 …（交易日）
    - 超過 FILL_WINDOW_DAYS 仍未站回 = 失敗；還沒走滿觀察期且未填息 = 未結案（不計入勝率）
    """
    if not bars or not dividends:
        return {"n": 0, "filled": 0, "failed": 0, "pending": 0, "avg_days": None, "success_rate": None, "events": []}
    dates = [b["date"] for b in bars]
    last = _d(asof or dates[-1])
    since = f"{last.year - FILL_LOOKBACK_YEARS}-{last.month:02d}-{last.day:02d}"
    events = []
    for dv in dividends:
        if dv["date"] < since:
            continue
        i0 = bisect_left(dates, dv["date"])
        if i0 >= len(bars):
            continue
        filled_days = None
        for k in range(i0, min(len(bars), i0 + FILL_WINDOW_DAYS)):
            if bars[k]["close"] >= dv["before"] - 1e-9:
                filled_days = k - i0 + 1
                break
        elapsed = len(bars) - i0
        if filled_days is not None:
            status = "filled"
        elif elapsed >= FILL_WINDOW_DAYS:
            status = "failed"
        else:
            status = "pending"
        events.append({"date": dv["date"], "amount": round(dv["amount"], 4), "days": filled_days, "status": status})
    filled = [e for e in events if e["status"] == "filled"]
    failed = [e for e in events if e["status"] == "failed"]
    pending = [e for e in events if e["status"] == "pending"]
    closed = len(filled) + len(failed)
    return {
        "n": len(events),
        "filled": len(filled),
        "failed": len(failed),
        "pending": len(pending),
        "avg_days": (sum(e["days"] for e in filled) / len(filled)) if filled else None,
        "success_rate": (len(filled) / closed) if closed else None,
        "events": events[-8:],
    }


# ═════════════════════════════════════════════════════════════════════════════
# 4. 五維評分
# ═════════════════════════════════════════════════════════════════════════════

def radar_scores(metrics: dict, div: dict, fill: dict) -> dict:
    """五維分數（0–100）。不適用（資料不足／不配息）的項目回 None，不假裝成 0 分。

    報酬潛力：有 3 年 CAGR 用它，否則用上市以來年化報酬（頁面會標「不足 3 年」）。
    總分 = 有值項目的平均（不配息的 ETF 不會因殖利率、填息 0 分被拉低）。
    """
    ret = metrics.get("cagr_3y")
    ret_basis = "cagr_3y"
    if ret is None:
        ret = metrics.get("ann_return")
        ret_basis = "ann_return"
    s_ret = _clamp(ret / RETURN_FULL_SCORE_AT, 0, 1) * 100 if ret is not None else None

    mdd = metrics.get("mdd")
    s_def = (_clamp(100 - (abs(mdd) * 100 - DEFENSE_BASE_MDD) * DEFENSE_SLOPE, DEFENSE_MIN, DEFENSE_MAX)
             if mdd is not None else None)

    sh = metrics.get("sharpe")
    s_sh = _clamp(sh / SHARPE_FULL_SCORE_AT, 0, 1) * 100 if sh is not None else None

    y = div.get("yield_ttm")
    s_y = _clamp(y / YIELD_FULL_SCORE_AT, 0, 1) * 100 if y is not None else None

    s_fill = None
    if fill.get("success_rate") is not None:
        speed = 0.0
        if fill.get("avg_days") is not None:
            speed = _clamp(1 - fill["avg_days"] / FILL_WINDOW_DAYS, 0, 1)
        s_fill = (0.6 * fill["success_rate"] + 0.4 * speed) * 100

    scores = {"return": s_ret, "defense": s_def, "sharpe": s_sh, "yield": s_y, "fill": s_fill}
    vals = [v for v in scores.values() if v is not None]
    scores["total"] = (sum(vals) / len(vals)) if vals else None
    scores["return_basis"] = ret_basis
    return {k: (round(v, 1) if isinstance(v, float) else v) for k, v in scores.items()}


# ═════════════════════════════════════════════════════════════════════════════
# 5. 急跌與反彈（取代 Gemini 版寫死的「2026 年 7 月」欄位）
# ═════════════════════════════════════════════════════════════════════════════

def find_drawdown_episode(bars: list[dict], adj: list[float], lookback_days: int = 180,
                          min_drop: float = 0.05) -> Optional[dict]:
    """在最近 lookback_days 天內，找基準（通常是 0050）最大的一段「高點→低點」回落。

    回傳 {start, end, drop}（日期為交易日）；跌幅不到 min_drop 回 None（沒有明顯急跌）。
    """
    if len(bars) < 20:
        return None
    dates = [b["date"] for b in bars]
    last = _d(dates[-1])
    since = (last - timedelta(days=lookback_days)).isoformat()
    i0 = max(bisect_left(dates, since), 0)
    peak_i, peak = i0, adj[i0]
    best = {"drop": 0.0, "start": None, "end": None}
    for i in range(i0, len(bars)):
        if adj[i] > peak:
            peak, peak_i = adj[i], i
        drop = adj[i] / peak - 1
        if drop < best["drop"]:
            best = {"drop": drop, "start": dates[peak_i], "end": dates[i]}
    if best["start"] is None or best["drop"] > -min_drop:
        return None
    return best


def event_window(bars: list[dict], dividends: list[dict], start: str, end: str,
                 rebound_end: Optional[str] = None) -> Optional[dict]:
    """某檔在 [start, end] 的急跌與其後反彈（價格是分割調整後、未含息的看盤價）。

    - 區間最高：[start, end] 內最高的日內高點（含日期）
    - 區間最低：最高點「之後」到 end 的最低日內低點（這樣跌幅一定是真的由高往低）
    - 反彈高點：最低點之後到 rebound_end 的最高日內高點；反彈 % = 反彈高點 / 最低 − 1
    - 區間內除息：這段期間的除息金額（價格跌幅裡有一部分是除息造成的，不是真的下跌）
    """
    if not bars:
        return None
    dates = [b["date"] for b in bars]
    rebound_end = rebound_end or dates[-1]
    i_s = bisect_left(dates, start)
    i_e = _idx_on_or_before(dates, end)
    if i_s >= len(bars) or i_e < i_s:
        return None
    window = bars[i_s:i_e + 1]
    hi_bar = max(window, key=lambda b: b["high"])
    hi_i = i_s + window.index(hi_bar)
    after_high = bars[hi_i:i_e + 1]
    lo_bar = min(after_high, key=lambda b: b["low"])
    lo_i = hi_i + after_high.index(lo_bar)
    i_r = _idx_on_or_before(dates, rebound_end)
    reb_bars = bars[lo_i + 1:i_r + 1]
    reb = max(reb_bars, key=lambda b: b["high"]) if reb_bars else None
    div_in = sum(d["amount"] for d in dividends if start <= d["date"] <= end)
    return {
        "high": hi_bar["high"], "high_date": hi_bar["date"],
        "low": lo_bar["low"], "low_date": lo_bar["date"],
        "drawdown": lo_bar["low"] / hi_bar["high"] - 1,
        "rebound_high": reb["high"] if reb else None,
        "rebound_date": reb["date"] if reb else None,
        "rebound_pct": (reb["high"] / lo_bar["low"] - 1) if reb else None,
        "dividends_in_window": round(div_in, 4),
        "partial": _d(dates[0]) > _d(start),  # 上市日比區間起點還晚
    }


# ═════════════════════════════════════════════════════════════════════════════
# 6. 一檔標的的完整整理
# ═════════════════════════════════════════════════════════════════════════════

def build_symbol_bundle(price_rows: list[dict], dividend_rows: list[dict], max_series_years: int = 5) -> Optional[dict]:
    """FinMind 原始資料 → 可快取的單檔整理結果（不含跨標的的事件視窗，那個要看基準）。

    回傳 None 代表完全沒有可用日線。
    """
    bars = clean_bars(price_rows)
    if len(bars) < 2:
        return None
    splits = detect_splits(bars)
    sbars = apply_splits(bars, splits)
    dividends = parse_dividends(dividend_rows, splits)
    adj = total_return_series(sbars, dividends)
    metrics = compute_metrics(sbars, adj)
    div = dividend_summary(sbars, dividends)
    fill = fill_stats(sbars, dividends)
    scores = radar_scores(metrics, div, fill)

    last = _d(sbars[-1]["date"])
    cut = (last - timedelta(days=int(365.25 * max_series_years) + 10)).isoformat()
    keep = [i for i, b in enumerate(sbars) if b["date"] >= cut]
    return {
        "metrics": metrics,
        "dividends": div,
        "fill": fill,
        "scores": scores,
        "splits": splits,
        # 走勢用：還原價（含息），前端依時間範圍重新以 100 起算
        "series": {"dates": [sbars[i]["date"] for i in keep], "adj": [round(adj[i], 4) for i in keep]},
        # 事件視窗用：看盤價的日內高低（只留近 2 年，夠用且省空間）
        "ohlc": [[b["date"], round(b["high"], 4), round(b["low"], 4), round(b["close"], 4)]
                 for b in sbars if b["date"] >= (last - timedelta(days=740)).isoformat()],
        "dividend_events": [{"date": d["date"], "amount": round(d["amount"], 4)} for d in dividends
                            if d["date"] >= (last - timedelta(days=740)).isoformat()],
    }


def bundle_event(bundle: dict, start: str, end: str, rebound_end: Optional[str] = None) -> Optional[dict]:
    """用快取的 bundle 算事件視窗（bundle['ohlc'] 是 [date, high, low, close]）。"""
    bars = [{"date": d, "high": h, "low": lo, "close": c, "open": c} for d, h, lo, c in bundle.get("ohlc", [])]
    divs = [{"date": e["date"], "amount": e["amount"]} for e in bundle.get("dividend_events", [])]
    return event_window(bars, divs, start, end, rebound_end)


def bundle_drawdown_episode(bundle: dict, lookback_days: int = 180, min_drop: float = 0.05) -> Optional[dict]:
    """用基準（0050）的 bundle 偵測最近一次明顯急跌。用還原價的收盤序列。"""
    s = bundle.get("series") or {}
    dates, adj = s.get("dates") or [], s.get("adj") or []
    bars = [{"date": d, "close": a} for d, a in zip(dates, adj)]
    return find_drawdown_episode(bars, adj, lookback_days, min_drop)


# ═════════════════════════════════════════════════════════════════════════════
# 7. ETF 分類（FinMind 沒有子類別，用名稱規則判斷；可用 OVERRIDES 手動修正）
# ═════════════════════════════════════════════════════════════════════════════

CATEGORY_OVERRIDES: dict[str, str] = {}  # 例如 {"00xxx": "dividend"}，規則判斷錯時在這裡修

_DIVIDEND_WORDS = ("高股息", "高息", "優息", "股利", "收益", "息")
_MARKET_WORDS = ("台灣50", "臺灣50", "台50", "TOP50", "領袖50", "市值", "加權", "中型100", "50")


def classify_etf(symbol: str, name: str) -> str:
    """回傳 active（主動型）／dividend（高股息）／market（市值型）／other（其他）。"""
    if symbol in CATEGORY_OVERRIDES:
        return CATEGORY_OVERRIDES[symbol]
    n = name or ""
    if n.startswith("主動") or "主動" in n:
        return "active"
    if any(w in n for w in _DIVIDEND_WORDS) and not n.endswith("債"):
        return "dividend"
    if any(w in n for w in _MARKET_WORDS):
        return "market"
    return "other"
