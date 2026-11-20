"""本地資料庫優先讀取層（app/data/db_reader.py + FinMindClient 整合）單元測試。

驗證重點：
1. 庫內資料命中（md_* 與全市場 od_*，以及兩者互補合併）時，完全不會呼叫 FinMind（呼叫次數為 0）。
2. 庫內無資料、起點涵蓋不足、或資料不夠新時，正確回落 FinMind。
3. MongoDB 連線異常或查詢逾時時，安全回落 FinMind、不拋 500。
4. 回傳 DataFrame 欄位名稱、日期格式、數值單位（特別是 od_revenue 千元→元）與欄位順序
   與原有 FinMind 介面 100% 相容，並可無縫通過既有個股／籌碼／評分卡流程。
5. stock_store.default_fetchers() 關閉本地讀庫（use_local_db=False），避免每日同步自我迴圈。
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.crawler.finmind_client import FinMindClient, _clear_cache
from app.crawler.fundamental import FundamentalCrawler
from app.crawler.institutional import InstitutionalCrawler
from app.crawler.stock_price import StockPriceCrawler
from app.data import db_reader as dr
from app.data import open_data as od
from app.data import stock_store as st

TODAY = date(2026, 11, 12)  # 星期四


def run(coro):
    return asyncio.run(coro)


# ───────────────────────── 假 MongoDB（支援 $gte/$lte/$lt/$gt）─────────────────────────

def _match(doc, flt):
    for k, v in (flt or {}).items():
        have = doc.get(k)
        if isinstance(v, dict):
            if "$in" in v and have not in v["$in"]:
                return False
            if "$gte" in v and not (have is not None and have >= v["$gte"]):
                return False
            if "$lte" in v and not (have is not None and have <= v["$lte"]):
                return False
            if "$lt" in v and not (have is not None and have < v["$lt"]):
                return False
            if "$gt" in v and not (have is not None and have > v["$gt"]):
                return False
        elif have != v:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=1):
        self.docs = sorted(
            self.docs,
            key=lambda d: (d.get(key) is None, d.get(key)),
            reverse=direction < 0,
        )
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        return [dict(d) for d in self.docs]


class FakeColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, flt, proj=None):
        return next((dict(d) for d in self.docs if _match(d, flt)), None)

    def find(self, flt=None, proj=None):
        out = []
        for d in self.docs:
            if _match(d, flt):
                item = dict(d)
                if proj and proj.get("_id") == 0:
                    item.pop("_id", None)
                out.append(item)
        return FakeCursor(out)


class FakeDB:
    def __init__(self):
        self.colls: dict[str, FakeColl] = {}

    def __getitem__(self, name: str) -> FakeColl:
        return self.colls.setdefault(name, FakeColl())


# ───────────────────────── 合成測試資料輔助 ─────────────────────────

def _weekdays(start: date, end: date) -> list[str]:
    out = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _seed_md_price(db: FakeDB, symbol: str, start: date, end: date, base: float = 100.0):
    now = datetime(2026, 11, 12, 8, 0)
    for idx, d in enumerate(_weekdays(start, end)):
        c = base + idx * 0.5
        db["md_price"].docs.append({
            "symbol": symbol,
            "date": d,
            "open": c - 0.5,
            "high": c + 1.0,
            "low": c - 1.0,
            "close": c,
            "volume": 10000 + idx * 100,
            "updated_at": now,
        })


def _seed_md_institutional(db: FakeDB, symbol: str, start: date, end: date):
    now = datetime(2026, 11, 12, 8, 0)
    for d in _weekdays(start, end):
        for name, buy, sell in (
            ("Foreign_Investor", 5000, 3000),
            ("Investment_Trust", 1200, 400),
            ("Dealer_self", 300, 200),
        ):
            db["md_institutional"].docs.append({
                "symbol": symbol,
                "date": d,
                "name": name,
                "buy": buy,
                "sell": sell,
                "updated_at": now,
            })


def _seed_md_margin(db: FakeDB, symbol: str, start: date, end: date, base_bal: int = 10000):
    now = datetime(2026, 11, 12, 8, 0)
    for idx, d in enumerate(_weekdays(start, end)):
        bal = base_bal + idx * 50
        db["md_margin"].docs.append({
            "symbol": symbol,
            "date": d,
            "MarginPurchaseBuy": 500,
            "MarginPurchaseCashRepayment": 10,
            "MarginPurchaseLimit": 500000,
            "MarginPurchaseSell": 440,
            "MarginPurchaseTodayBalance": bal,
            "MarginPurchaseYesterdayBalance": bal - 50,
            "OffsetLoanAndShort": 20,
            "ShortSaleBuy": 5,
            "ShortSaleCashRepayment": 0,
            "ShortSaleLimit": 500000,
            "ShortSaleSell": 10,
            "ShortSaleTodayBalance": 300 + idx,
            "ShortSaleYesterdayBalance": 299 + idx,
            "Note": "",
            "updated_at": now,
        })


def _seed_od_margin(db: FakeDB, symbol: str, start: date, end: date, base_bal: int = 12000):
    for idx, d in enumerate(_weekdays(start, end)):
        bal = base_bal + idx * 30
        db["od_margin"].docs.append({
            "mkt": "twse",
            "symbol": symbol,
            "date": d,
            "margin_buy": 400,
            "margin_sell": 370,
            "margin_repay": 0,
            "margin_prev": bal - 30,
            "margin_bal": bal,
            "margin_limit": 400000,
            "short_cover": 10,
            "short_sell": 15,
            "short_repay": 0,
            "short_prev": 200 + idx - 1,
            "short_bal": 200 + idx,
            "short_limit": 400000,
            "offset": 12,
        })


def _seed_md_valuation(db: FakeDB, symbol: str, start: date, end: date):
    now = datetime(2026, 11, 12, 8, 0)
    for d in _weekdays(start, end):
        db["md_valuation"].docs.append({
            "symbol": symbol,
            "date": d,
            "PER": 18.5,
            "PBR": 3.2,
            "dividend_yield": 3.4,
            "updated_at": now,
        })


def _seed_od_valuation(db: FakeDB, symbol: str, start: date, end: date, pe=16.2, pb=2.1, dy=4.1):
    for d in _weekdays(start, end):
        db["od_valuation"].docs.append({
            "mkt": "tpex",
            "symbol": symbol,
            "date": d,
            "pe": pe,
            "pb": pb,
            "dy": dy,
        })


def _seed_md_revenue(db: FakeDB, symbol: str, months: list[tuple[int, int]], rev_yuan: float = 1_000_000_000.0):
    now = datetime(2026, 11, 12, 8, 0)
    for idx, (y, m) in enumerate(months):
        fm_date = dr.ym_to_finmind_date(f"{y:04d}-{m:02d}")
        db["md_revenue"].docs.append({
            "symbol": symbol,
            "date": fm_date,
            "country": "Taiwan",
            "revenue": rev_yuan + idx * 10_000_000.0,
            "revenue_year": y,
            "revenue_month": m,
            "create_time": f"{fm_date[:8]}10 15:00:00",
            "updated_at": now,
        })


def _seed_od_revenue(db: FakeDB, symbol: str, months: list[tuple[int, int]], rev_k: float = 1_000_000.0):
    """官方開放資料月營收：單位為千元（rev_k=1_000_000 代表 10 億元）。"""
    for idx, (y, m) in enumerate(months):
        ym = f"{y:04d}-{m:02d}"
        fm_date = dr.ym_to_finmind_date(ym)
        db["od_revenue"].docs.append({
            "mkt": "twse",
            "symbol": symbol,
            "ym": ym,
            "report_date": f"{fm_date[:8]}10",
            "rev": rev_k + idx * 50_000.0,
            "yoy": 12.5,
        })


@pytest.fixture(autouse=True)
def _reset_state():
    dr.reset_cooldown()
    _clear_cache()
    yield
    dr.reset_cooldown()
    _clear_cache()


def _patch_fake_db(monkeypatch, db: FakeDB, today: date = TODAY):
    async def _get_db():
        return db

    monkeypatch.setattr(st, "_db", _get_db)
    monkeypatch.setattr(od, "_db", _get_db)
    monkeypatch.setattr(od, "tw_today", lambda: today)


# ───────────────────────── 1. 純函式：日期、覆蓋度、格式轉換 ─────────────────────────

def test_business_days_and_last_weekday():
    assert dr.last_weekday(date(2026, 11, 14)) == date(2026, 11, 13)  # 週六 → 週五
    assert dr.last_weekday(date(2026, 11, 15)) == date(2026, 11, 13)  # 週日 → 週五
    assert dr.last_weekday(date(2026, 11, 12)) == date(2026, 11, 12)  # 週四不變
    assert dr.business_days_between(date(2026, 11, 6), date(2026, 11, 6)) == 0
    assert dr.business_days_between(date(2026, 11, 6), date(2026, 11, 9)) == 1   # 週五 → 週一 = 1 營業日
    assert dr.business_days_between(date(2026, 11, 6), date(2026, 11, 10)) == 2  # 週五 → 週二 = 2 營業日
    assert dr.business_days_between(date(2026, 11, 12), date(2026, 11, 10)) == 0


def test_is_daily_covered_rules():
    # 完整區間命中（含落後 1 營業日，如盤中或融資延遲）
    dates = _weekdays(date(2026, 8, 1), date(2026, 11, 11))
    assert dr.is_daily_covered(dates, "2026-08-01", "2026-11-12", today=TODAY) is True
    # 週末請求：庫到週五即命中
    sat = date(2026, 11, 14)
    assert dr.is_daily_covered(_weekdays(date(2026, 8, 1), date(2026, 11, 13)), "2026-08-01", "2026-11-14", today=sat) is True
    # 落後 2 營業日（停在週二，今天週四）→ 不夠新，回落
    stale = _weekdays(date(2026, 8, 1), date(2026, 11, 10))
    assert dr.is_daily_covered(stale, "2026-08-01", "2026-11-12", today=TODAY) is False
    # 請求起點早於庫內（評分卡查 3 年但庫內只有 100 天）→ 起點不足，回落
    assert dr.is_daily_covered(dates, "2023-11-01", "2026-11-12", today=TODAY) is False
    # 短區間（10 天）庫內僅有最新 1 天且無更早紀錄 → 不可誤判命中
    assert dr.is_daily_covered(["2026-11-12"], "2026-11-02", "2026-11-12", today=TODAY) is False
    # 歷史區間：庫內已有更晚紀錄（has_later=True）→ 即使結尾碰到連假仍命中
    hist = _weekdays(date(2026, 6, 1), date(2026, 6, 26))
    assert dr.is_daily_covered(hist, "2026-06-01", "2026-06-30", today=TODAY, has_later=True) is True


def test_monthly_revenue_date_and_coverage():
    assert dr.ym_to_finmind_date("2026-10") == "2026-11-01"
    assert dr.ym_to_finmind_date("2025-12") == "2026-01-01"
    # 15 號前容許只到上上個月（2026-11-12 → 預期至少 2026-10-01）
    assert dr.expected_latest_revenue_date(date(2026, 11, 12)) == date(2026, 10, 1)
    # 15 號起要求上個月已公布（2026-11-15 → 預期至少 2026-11-01）
    assert dr.expected_latest_revenue_date(date(2026, 11, 15)) == date(2026, 11, 1)
    # 跨年 1 月 10 號 → 預期至少前一年 12 月 1 號
    assert dr.expected_latest_revenue_date(date(2026, 1, 10)) == date(2025, 12, 1)

    dates = [f"2026-{m:02d}-01" for m in range(1, 11)]  # 到 2026-10-01（9 月營收）
    assert dr.is_monthly_covered(dates, "2026-01-01", "2026-11-12", today=date(2026, 11, 12)) is True
    assert dr.is_monthly_covered(dates, "2026-01-01", "2026-11-20", today=date(2026, 11, 20)) is False
    assert dr.is_monthly_covered(dates, "2024-01-01", "2026-11-12", today=date(2026, 11, 12)) is False


def test_od_conversions_match_finmind_schema_and_units():
    # 1. od_margin：YesterdayBalance 必須排在 TodayBalance 之前，確保 major_players 迴圈取到今日餘額
    m_df = dr.od_margin_to_df([{
        "mkt": "twse", "symbol": "2330", "date": "2026-11-12",
        "margin_buy": 100, "margin_sell": 80, "margin_repay": 5, "margin_prev": 1000, "margin_bal": 1015, "margin_limit": 50000,
        "short_cover": 2, "short_sell": 4, "short_repay": 0, "short_prev": 50, "short_bal": 52, "short_limit": 50000, "offset": 3,
    }])
    cols = list(m_df.columns)
    assert cols.index("MarginPurchaseYesterdayBalance") < cols.index("MarginPurchaseTodayBalance")
    assert cols.index("ShortSaleYesterdayBalance") < cols.index("ShortSaleTodayBalance")
    assert m_df.iloc[0]["MarginPurchaseTodayBalance"] == 1015
    assert m_df.iloc[0]["ShortSaleTodayBalance"] == 52
    assert m_df.iloc[0]["stock_id"] == "2330"

    # 2. od_valuation：虧損股 pe=None 保留缺失值（不亂補 0）
    v_df = dr.od_valuation_to_df([{"mkt": "twse", "symbol": "2409", "date": "2026-11-12", "pe": None, "pb": 0.75, "dy": None}])
    assert list(v_df.columns) == ["date", "stock_id", "dividend_yield", "PER", "PBR"]
    assert pd.isna(v_df.iloc[0]["PER"]) and pd.isna(v_df.iloc[0]["dividend_yield"])
    assert v_df.iloc[0]["PBR"] == 0.75

    # 3. od_revenue：千元轉元（×1000）、ym 轉次月 1 日、report_date 轉 create_time
    r_df = dr.od_revenue_to_df(
        [{"mkt": "twse", "symbol": "1101", "ym": "2026-10", "report_date": "2026-11-10", "rev": 16357176}],
        start="2026-10-15", end="2026-11-15",
    )
    assert len(r_df) == 1
    row = r_df.iloc[0]
    assert row["date"] == "2026-11-01"
    assert row["stock_id"] == "1101"
    assert row["revenue"] == 16357176 * 1000.0
    assert row["revenue_year"] == 2026 and row["revenue_month"] == 10
    assert row["create_time"] == "2026-11-10"


# ───────────────────────── 2. 命中本地 DB：FinMind 呼叫次數為 0 ─────────────────────────

def test_all_five_md_datasets_hit_without_calling_finmind(monkeypatch):
    db = FakeDB()
    start_d = date(2026, 8, 1)
    _seed_md_price(db, "2330", start_d, TODAY)
    _seed_md_institutional(db, "2330", start_d, TODAY)
    _seed_md_margin(db, "2330", start_d, TODAY)
    _seed_md_valuation(db, "2330", start_d, TODAY)
    months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 11)]
    _seed_md_revenue(db, "2330", months)
    _patch_fake_db(monkeypatch, db)

    fetch_calls = []

    async def spy_fetch(self, dataset, params):
        fetch_calls.append((dataset, params))
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", spy_fetch)
    client = FinMindClient()

    price_df = run(client.get_stock_price("2330", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "md_price"
    assert list(price_df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert pd.api.types.is_datetime64_any_dtype(price_df["date"])
    assert not price_df.empty

    inst_df = run(client.get_institutional_investors("2330", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "md_institutional"
    assert {"date", "stock_id", "name", "buy", "sell"} <= set(inst_df.columns)
    assert "updated_at" not in inst_df.columns

    margin_df = run(client.get_margin_trading("2330", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "md_margin"
    assert {"date", "stock_id", "MarginPurchaseTodayBalance", "ShortSaleTodayBalance"} <= set(margin_df.columns)

    val_df = run(client.get_valuation("2330", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "md_valuation"
    assert {"date", "stock_id", "PER", "PBR", "dividend_yield"} <= set(val_df.columns)

    rev_df = run(client.get_monthly_revenue("2330", "2025-02-01", "2026-11-12"))
    assert client.last_read_source == "md_revenue"
    assert {"date", "stock_id", "revenue", "revenue_year", "revenue_month"} <= set(rev_df.columns)

    # 關鍵驗證：5 個資料集全命中本地庫，FinMind _fetch 呼叫次數為 0！
    assert len(fetch_calls) == 0


def test_non_whitelist_stock_hits_open_data_od_collections_without_finmind(monkeypatch):
    """非白名單股票（md_* 無資料）只要 od_margin / od_valuation / od_revenue 涵蓋，仍 0 次 FinMind。"""
    db = FakeDB()
    start_d = date(2026, 9, 1)
    _seed_od_margin(db, "3105", start_d, TODAY)
    _seed_od_valuation(db, "3105", start_d, TODAY)
    months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 11)]
    _seed_od_revenue(db, "3105", months, rev_k=1_234_567.0)
    _patch_fake_db(monkeypatch, db)

    fetch_calls = []

    async def spy_fetch(self, dataset, params):
        fetch_calls.append((dataset, params))
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", spy_fetch)
    client = FinMindClient()

    m_df = run(client.get_margin_trading("3105", "2026-09-01", "2026-11-12"))
    assert client.last_read_source == "od_margin" and not m_df.empty

    v_df = run(client.get_valuation("3105", "2026-09-01", "2026-11-12"))
    assert client.last_read_source == "od_valuation" and v_df.iloc[-1]["PER"] == 16.2

    r_df = run(client.get_monthly_revenue("3105", "2025-02-01", "2026-11-12"))
    assert client.last_read_source == "od_revenue" and r_df.iloc[0]["revenue"] == 1_234_567_000.0

    assert len(fetch_calls) == 0


def test_md_and_od_merge_complement_avoids_finmind(monkeypatch):
    """md_margin 有歷史但落後 4 天 + od_margin 補上近 5 天最新 → 合併命中，0 次 FinMind！"""
    db = FakeDB()
    _seed_md_margin(db, "2330", date(2026, 8, 1), date(2026, 11, 6), base_bal=10000)
    _seed_od_margin(db, "2330", date(2026, 11, 5), TODAY, base_bal=20000)
    _patch_fake_db(monkeypatch, db)

    fetch_calls = []

    async def spy_fetch(self, dataset, params):
        fetch_calls.append((dataset, params))
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", spy_fetch)
    client = FinMindClient()

    df = run(client.get_margin_trading("2330", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "md+od_margin"
    assert len(fetch_calls) == 0
    # 重疊日（2026-11-06）保留 md_margin 的資料，最新日（2026-11-12）由 od_margin 補上
    assert df.iloc[-1]["date"] == "2026-11-12"
    row_1106 = df[df["date"] == "2026-11-06"].iloc[0]
    assert row_1106["MarginPurchaseTodayBalance"] < 20000


# ───────────────────────── 3. 無資料 / 涵蓋不足 → 正確回落 FinMind ─────────────────────────

def test_fallback_to_finmind_when_missing_or_insufficient_range(monkeypatch):
    db = FakeDB()
    # 庫內 2330 的估值只有近 5 天，不足以涵蓋評分卡 3 年區間
    _seed_od_valuation(db, "2330", date(2026, 11, 6), TODAY)
    # 庫內 2330 的日線停在 2026-11-05（落後 5 營業日，不夠新）
    _seed_md_price(db, "2330", date(2026, 8, 1), date(2026, 11, 5))
    _patch_fake_db(monkeypatch, db)

    fetch_calls = []

    async def fake_fetch(self, dataset, params):
        fetch_calls.append((dataset, params["data_id"]))
        if dataset == "TaiwanStockPrice":
            return pd.DataFrame([{"date": "2026-11-12", "open": 1000, "max": 1010, "min": 995, "close": 1005, "Trading_Volume": 50000}])
        if dataset == "TaiwanStockPER":
            return pd.DataFrame([{"date": "2026-11-12", "stock_id": params["data_id"], "PER": 20.0, "PBR": 5.0, "dividend_yield": 1.8}])
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)
    client = FinMindClient()

    # 1. 庫內完全無該檔（9999）→ 回落 FinMind
    df1 = run(client.get_stock_price("9999", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "finmind" and not df1.empty

    # 2. 庫內 2330 日線過舊（停在 11/05）→ 回落 FinMind
    df2 = run(client.get_stock_price("2330", "2026-08-01", "2026-11-12"))
    assert client.last_read_source == "finmind" and df2.iloc[-1]["close"] == 1005

    # 3. 評分卡請求 3 年估值，庫內只有 5 天 → 回落 FinMind
    df3 = run(client.get_valuation("2330", "2023-11-01", "2026-11-12"))
    assert client.last_read_source == "finmind" and df3.iloc[-1]["PER"] == 20.0

    assert fetch_calls == [
        ("TaiwanStockPrice", "9999"),
        ("TaiwanStockPrice", "2330"),
        ("TaiwanStockPER", "2330"),
    ]


# ───────────────────────── 4. MongoDB 異常／逾時安全回落 ─────────────────────────

def test_mongodb_exception_and_timeout_safely_fallback_without_500(monkeypatch):
    async def boom_db():
        raise RuntimeError("MongoDB connection refused")

    monkeypatch.setattr(st, "_db", boom_db)
    monkeypatch.setattr(od, "_db", boom_db)

    fetch_calls = []

    async def fake_fetch(self, dataset, params):
        fetch_calls.append(dataset)
        return pd.DataFrame([{"date": "2026-11-12", "open": 500, "max": 510, "min": 495, "close": 505, "Trading_Volume": 12345}])

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)

    # 直接透過 FastAPI stock price 端點驗證不會拋 500
    from app.api.stock import router as stock_router

    app = FastAPI()
    app.include_router(stock_router)
    http = TestClient(app)
    resp = http.get("/api/v1/stocks/2330/price?start=2026-10-01&end=2026-11-12")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["symbol"] == "2330" and body["source"] == "finmind"
    assert body["items"][-1]["close"] == 505.0
    assert fetch_calls == ["TaiwanStockPrice"]

    # 測試查詢逾時也能安全回落不卡死
    dr.reset_cooldown()
    monkeypatch.setattr(dr, "DB_READ_TIMEOUT_SEC", 0.05)

    async def slow_db():
        await asyncio.sleep(2.0)
        return FakeDB()

    monkeypatch.setattr(st, "_db", slow_db)
    client = FinMindClient()
    df = run(client.get_stock_price("2330", "2026-10-01", "2026-11-12"))
    assert client.last_read_source == "finmind" and df.iloc[-1]["close"] == 505.0


# ───────────────────────── 5. 同步排程防自我迴圈 ─────────────────────────

def test_stock_store_default_fetchers_bypass_local_db(monkeypatch):
    """stock_store.default_fetchers() 必須直接打 FinMind，不能讀回本地 md_*。"""
    db = FakeDB()
    _seed_md_price(db, "2330", date(2026, 8, 1), TODAY)
    _patch_fake_db(monkeypatch, db)

    fetch_calls = []

    async def spy_fetch(self, dataset, params):
        fetch_calls.append(dataset)
        return pd.DataFrame([{"date": "2026-11-12", "open": 999, "max": 1000, "min": 990, "close": 995, "Trading_Volume": 888}])

    monkeypatch.setattr(FinMindClient, "_fetch", spy_fetch)
    fetchers = st.default_fetchers()
    df = run(fetchers["price"]("2330", "2026-08-01", "2026-11-12"))
    assert fetch_calls == ["TaiwanStockPrice"]
    assert df.iloc[0]["close"] == 995


# ───────────────────────── 6. 下游個股／籌碼／評分卡整合相容性 ─────────────────────────

def test_downstream_crawlers_and_major_players_use_local_db_with_zero_finmind(monkeypatch):
    db = FakeDB()
    start_d = date(2026, 6, 1)
    _seed_md_price(db, "2330", start_d, TODAY)
    _seed_md_institutional(db, "2330", start_d, TODAY)
    _seed_od_margin(db, "2330", start_d, TODAY, base_bal=15000)
    months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 11)]
    _seed_od_revenue(db, "2330", months, rev_k=2_000_000.0)
    _patch_fake_db(monkeypatch, db)

    fetch_calls = []

    async def forbid_fetch(self, dataset, params):
        fetch_calls.append((dataset, params))
        raise AssertionError(f"不應呼叫 FinMind: {dataset}")

    monkeypatch.setattr(FinMindClient, "_fetch", forbid_fetch)

    # 1. StockPriceCrawler（含週線 resample 與 last_source == 'finmind' 相容）
    price_crawler = StockPriceCrawler()
    w_df = run(price_crawler.get_price("2330.TW", "2026-07-01", "2026-11-12", period="1w"))
    assert price_crawler.last_source == "finmind"
    assert not w_df.empty and list(w_df.columns) == ["date", "open", "high", "low", "close", "volume"]

    # 2. InstitutionalCrawler（md_institutional + od_margin）
    chip = run(InstitutionalCrawler().get_chip_data("2330", "2026-08-01", "2026-11-12"))
    assert len(chip["items"]) > 40 and len(chip["margin"]) > 40
    assert chip["margin"][0]["margin_balance"] >= 15000
    assert chip["summary"]["foreign_buy_streak"] > 0

    # 3. FundamentalCrawler（od_revenue 千元→元 + YoY 計算）
    revs = run(FundamentalCrawler().get_monthly_revenue("2330", "2025-02-01", "2026-11-12"))
    assert len(revs) >= 20
    assert revs[-1]["month"] == "2026-10"
    assert revs[-1]["revenue"] > 2_000_000_000.0  # 千元已正確轉為元
    assert revs[-1]["yoy"] is not None

    # 4. analyze_major_players（md_price + md_institutional + od_margin）
    from app.analysis import major_players as mp

    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    monkeypatch.setattr(mp, "date", FixedDate)
    major = run(mp.analyze_major_players("2330", days=90))
    assert "error" not in major
    assert major["margin_analysis"]["summary"]["margin_balance_latest"] >= 15000
    assert len(major["institutional_flow"]["foreign"]) > 0

    assert fetch_calls == []


def test_scorecard_uses_local_db_for_covered_datasets(monkeypatch):
    """評分卡對庫內涵蓋的日線、大盤、估值、月營收、法人、融資皆 0 次打 FinMind。"""
    from app.analysis import stock_scorecard as sc
    from app.api import chip as chip_api

    db = FakeDB()
    # 建足 3 年多估值與 450 天日線、2 年多月營收
    _seed_md_price(db, "2330", TODAY - timedelta(days=450), TODAY, base=500.0)
    _seed_md_price(db, "TAIEX", TODAY - timedelta(days=60), TODAY, base=20000.0)
    _seed_md_valuation(db, "2330", TODAY - timedelta(days=365 * 3 + 30), TODAY)
    months = [(y, m) for y in (2024, 2025) for m in range(1, 13)] + [(2026, m) for m in range(1, 11)]
    _seed_md_revenue(db, "2330", months)
    _patch_fake_db(monkeypatch, db)

    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    # 讓 build_scorecard 裡的 date.today() 對齊 TODAY（2026-11-12）
    import datetime as dt_mod
    real_date = dt_mod.date

    fetch_datasets = []

    async def spy_fetch(self, dataset, params):
        fetch_datasets.append(dataset)
        if dataset == "TaiwanStockInfo":
            return pd.DataFrame([{"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業"}])
        # 財報／外資持股本來不在 md_*/od_* 中，回空即可
        return pd.DataFrame()

    async def fake_chip(symbol, days):
        return {"major_players": None}

    monkeypatch.setattr(FinMindClient, "_fetch", spy_fetch)
    monkeypatch.setattr(chip_api, "_build_chip_analysis", fake_chip)

    # 覆寫 stock_scorecard.build_scorecard 內的 date.today：用簡單日期對齊即可，
    # 改直接把測試資料也延伸到真實 date.today()，避免 patch 內建 datetime.date
    real_today = real_date.today()
    if real_today != TODAY:
        db2 = FakeDB()
        _seed_md_price(db2, "2330", real_today - timedelta(days=450), real_today, base=500.0)
        _seed_md_price(db2, "TAIEX", real_today - timedelta(days=60), real_today, base=20000.0)
        _seed_md_valuation(db2, "2330", real_today - timedelta(days=365 * 3 + 30), real_today)
        m_list = []
        y0, m0 = real_today.year - 2, 1
        while (y0, m0) <= (real_today.year, real_today.month):
            m_list.append((y0, m0))
            y0, m0 = dr._shift_month(y0, m0, 1)
        _seed_md_revenue(db2, "2330", m_list)
        _patch_fake_db(monkeypatch, db2, today=real_today)

    card = run(sc.build_scorecard("2330"))
    assert card["applicable"] is True and card["symbol"] == "2330"
    assert card["meta"]["failed"] == []
    # 這 4 種本地已涵蓋的資料集絕不可出現在 FinMind 呼叫清單！
    for local_ds in ("TaiwanStockPrice", "TaiwanStockPER", "TaiwanStockMonthRevenue"):
        assert local_ds not in fetch_datasets
    # 確認基本面的估值與營收檢核項目都有成功算出（非 NA）
    fund = next(d for d in card["dimensions"] if d["key"] == "fundamental")
    by_id = {i["id"]: i for i in fund["items"]}
    assert by_id["F1"]["status"] in (sc.PASS, sc.FAIL)
    assert by_id["F3"]["status"] == sc.PASS  # dividend_yield=3.4 >= 3%
    assert by_id["F4"]["status"] in (sc.PASS, sc.FAIL)


def test_stock_calendar_reads_od_revenue_create_time(monkeypatch):
    """api/analysis.py 行事曆應能直接消費 od_revenue 轉出的 create_time 欄位。"""
    from app.api.analysis import router as analysis_router

    db = FakeDB()
    real_today = date.today()
    # calendar 請求近 400 天，種子資料從 430 天前開始涵蓋整段區間
    start_m = real_today - timedelta(days=430)
    months = []
    y, m = start_m.year, start_m.month
    while (y, m) <= (real_today.year, real_today.month):
        months.append((y, m))
        y, m = dr._shift_month(y, m, 1)
    _seed_od_revenue(db, "2330", months, rev_k=300_000_000.0)
    _patch_fake_db(monkeypatch, db, today=real_today)

    fetch_datasets = []

    async def spy_fetch(self, dataset, params):
        fetch_datasets.append(dataset)
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", spy_fetch)

    app = FastAPI()
    app.include_router(analysis_router)
    http = TestClient(app)
    resp = http.get("/api/v1/analysis/2330/calendar")
    assert resp.status_code == 200
    events = resp.json()["data"]["events"]
    rev_events = [e for e in events if e["type"] == "revenue" and not e["estimated"]]
    assert len(rev_events) >= 1
    assert "億元" in rev_events[-1]["detail"]
    assert "TaiwanStockMonthRevenue" not in fetch_datasets
