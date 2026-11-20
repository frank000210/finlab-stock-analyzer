"""T-020：AI 選股、關聯圖、類股輪動與 TaiwanStockInfo 省額度與防污染改造單元測試。"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analysis import nl_screener, peer_compare, sector_rotation, watch_graph
from app.api import graph as graph_api
from app.api import rotation as rotation_api
from app.crawler import finmind_client as fm_mod
from app.crawler.finmind_client import FinMindClient, _clear_cache
from app.crawler.stock_price import StockPriceCrawler
from app.data import db_reader as dr
from app.data import open_data as od
from app.data import stock_store as st
from app.db import cache as cache_mod
from app.db.memcache import mem_clear


def run(coro):
    return asyncio.run(coro)


# ───────────────────────── 輕量 Fake MongoDB（含 upsert / bulk_write / TTL cache）─────────────────────────

def _match(doc: dict, flt: dict | None) -> bool:
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
    def __init__(self, docs: list[dict]):
        self.docs = docs

    def sort(self, key, direction=1):
        self.docs = sorted(
            self.docs,
            key=lambda d: (d.get(key) is None, d.get(key)),
            reverse=direction < 0,
        )
        return self

    def limit(self, n: int):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        return [dict(d) for d in self.docs]


class FakeColl:
    def __init__(self):
        self.docs: list[dict] = []

    async def create_index(self, *args, **kwargs):
        return "idx"

    async def find_one(self, flt: dict, proj: dict | None = None):
        for d in self.docs:
            if _match(d, flt):
                out = dict(d)
                if proj and proj.get("_id") == 0:
                    out.pop("_id", None)
                return out
        return None

    def find(self, flt: dict | None = None, proj: dict | None = None):
        out = []
        for d in self.docs:
            if _match(d, flt):
                item = dict(d)
                if proj and proj.get("_id") == 0:
                    item.pop("_id", None)
                out.append(item)
        return FakeCursor(out)

    async def update_one(self, flt: dict, update: dict, upsert: bool = False):
        for d in self.docs:
            if _match(d, flt):
                if "$set" in update:
                    d.update(update["$set"])
                return
        if upsert:
            doc = dict(flt)
            if "$set" in update:
                doc.update(update["$set"])
            self.docs.append(doc)

    async def bulk_write(self, ops: list[Any], ordered: bool = False):
        for op in ops:
            await self.update_one(op._filter, op._doc, upsert=bool(op._upsert))


class FakeDB:
    def __init__(self):
        self._colls: dict[str, FakeColl] = {}

    def __getitem__(self, name: str) -> FakeColl:
        return self._colls.setdefault(name, FakeColl())

    def __getattr__(self, name: str) -> FakeColl:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


def _weekdays(start: date, end: date) -> list[str]:
    out = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _seed_md_price(db: FakeDB, symbol: str, start: date, end: date, base: float = 100.0, slope: float = 0.5):
    for idx, d in enumerate(_weekdays(start, end)):
        c = base + idx * slope + (1.5 if idx % 3 == 0 else -0.4)
        db["md_price"].docs.append({
            "symbol": symbol,
            "date": d,
            "open": c - 0.5,
            "high": c + 1.0,
            "low": c - 1.0,
            "close": c,
            "volume": 10000 + idx * 50,
        })


def _seed_md_institutional(db: FakeDB, symbol: str, start: date, end: date, phase: int = 0):
    for idx, d in enumerate(_weekdays(start, end)):
        val = 5000 + ((idx + phase) % 7) * 800
        db["md_institutional"].docs.append({
            "symbol": symbol,
            "date": d,
            "name": "Foreign_Investor",
            "buy": val,
            "sell": 3000,
        })


def _bind_db(monkeypatch, db: FakeDB):
    async def _get():
        return db

    monkeypatch.setattr(cache_mod, "get_mongodb", _get)
    monkeypatch.setattr(st, "_db", _get)
    monkeypatch.setattr(od, "_db", _get)
    monkeypatch.setattr(watch_graph, "get_mongodb", _get)
    monkeypatch.setattr(sector_rotation, "get_mongodb", _get)


@pytest.fixture(autouse=True)
def _clean_state():
    _clear_cache()
    mem_clear("")
    dr.reset_cooldown()
    graph_api._last_build_at = 0.0
    rotation_api._last_build_at = 0.0
    yield
    _clear_cache()
    mem_clear("")
    dr.reset_cooldown()


# ───────────────────────── 1. P1-2: TaiwanStockInfo 長效快取與過期舊表回退 ─────────────────────────

def test_stock_info_memory_mongo_and_stale_fallback(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    calls = []

    async def fake_fetch(self, dataset, params):
        calls.append(dataset)
        return pd.DataFrame([
            {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"},
            {"stock_id": "2317", "stock_name": "鴻海", "industry_category": "其他電子業", "type": "twse"},
        ])

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)

    client = FinMindClient()
    # 1. 冷啟動打一次 FinMind，同時寫入記憶體與 Mongo（fresh + stale）
    df1 = run(client.get_stock_info())
    assert len(df1) == 2 and calls == ["TaiwanStockInfo"]
    assert client.last_read_source == "finmind"

    # 2. 第二次直接命中程序內快取（0 FinMind）
    df2 = run(client.get_stock_info())
    assert len(df2) == 2 and calls == ["TaiwanStockInfo"]
    assert client.last_read_source == "memory_stock_info"

    # 3. 模擬服務重啟（清程序內快取），仍命中 Mongo 24h 快取（0 FinMind）
    _clear_cache()
    df3 = run(client.get_stock_info())
    assert len(df3) == 2 and calls == ["TaiwanStockInfo"]
    assert client.last_read_source == "mongo_stock_info"

    # 4. 模擬 24h 快取過期且 FinMind 額度耗盡（HTTP 429），安全回退 Mongo 7 天舊表
    _clear_cache()
    db.cache.docs = [d for d in db.cache.docs if d.get("key") != fm_mod._STOCK_INFO_CACHE_KEY]

    async def quota_fetch(self, dataset, params):
        calls.append(f"ERR:{dataset}")
        raise ValueError("FinMind request failed: HTTP 429")

    monkeypatch.setattr(FinMindClient, "_fetch", quota_fetch)
    df4 = run(client.get_stock_info())
    assert len(df4) == 2
    assert client.last_read_source == "stale_stock_info"


# ───────────────────────── 2. P0-1 & P1-2: _one_metrics 單檔快取 + AI 選股兩階段初篩 ─────────────────────────

def test_one_metrics_options_single_stock_cache_and_upgrade(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    fetch_log = []

    async def fake_fetch(self, dataset, params):
        fetch_log.append((dataset, params.get("data_id")))
        today_s = date.today().isoformat()
        if dataset == "TaiwanStockPrice":
            return pd.DataFrame([
                {"date": (date.today() - timedelta(days=i)).isoformat(), "open": 100, "max": 105, "min": 95, "close": 100 + i * 0.1, "Trading_Volume": 10000}
                for i in range(25, -1, -1)
            ])
        if dataset == "TaiwanStockPER":
            return pd.DataFrame([{"date": today_s, "stock_id": params["data_id"], "PER": 15.0, "PBR": 2.1, "dividend_yield": 3.5}])
        if dataset == "TaiwanStockMonthRevenue":
            y = date.today().year
            return pd.DataFrame([
                {"date": f"{y - 1}-09-01", "revenue_year": y - 1, "revenue_month": 8, "revenue": 100},
                {"date": f"{y}-09-01", "revenue_year": y, "revenue_month": 8, "revenue": 120},
            ])
        if dataset == "TaiwanStockFinancialStatements":
            return pd.DataFrame([
                {"date": f"{date.today().year}-06-30", "type": "EPS", "value": 4.2},
                {"date": f"{date.today().year}-06-30", "type": "Revenue", "value": 1000},
                {"date": f"{date.today().year}-06-30", "type": "GrossProfit", "value": 450},
            ])
        if dataset == "TaiwanStockShareholding":
            return pd.DataFrame([{"date": today_s, "NumberOfSharesIssued": 1_000_000_000}])
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)

    # 1. 選股模式（不抓市值）：不應呼叫 TaiwanStockShareholding
    r1 = run(peer_compare._one_metrics("2330", "台積電", "screener", include_market_cap=False, include_financials=True))
    assert r1["pe"] == 15.0 and r1["gross_margin"] == 45.0
    assert "market_cap" not in r1
    assert all(ds != "TaiwanStockShareholding" for ds, _ in fetch_log)

    # 2. 再次以相同選項呼叫（即使清空 FinMind 5 分鐘記憶體快取）：命中單檔 Mongo 快取，0 次 FinMind
    _clear_cache()
    fetch_log.clear()
    r2 = run(peer_compare._one_metrics("2330", "台積電", "screener", include_market_cap=False, include_financials=True))
    assert r2["pe"] == 15.0 and fetch_log == []

    # 3. 升級為同業比較模式（需要市值）：只補抓 TaiwanStockShareholding 1 次，其餘全部複用快取
    r3 = run(peer_compare._one_metrics("2330", "台積電", "target", include_market_cap=True, include_financials=True))
    assert r3["market_cap"] is not None
    assert fetch_log == [("TaiwanStockShareholding", "2330")]


def test_peer_comparison_cache_hit_calls_zero_finmind(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    fetch_log = []

    async def fake_fetch(self, dataset, params):
        fetch_log.append(dataset)
        if dataset == "TaiwanStockInfo":
            return pd.DataFrame([
                {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業"},
                {"stock_id": "2454", "stock_name": "聯發科", "industry_category": "半導體業"},
            ])
        if dataset == "TaiwanStockPER":
            return pd.DataFrame([{"date": date.today().isoformat(), "PER": 18.0, "PBR": 3.0, "dividend_yield": 2.5}])
        return pd.DataFrame()

    async def fake_quotes():
        return {"2330": 1e10, "2454": 5e9}

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)
    monkeypatch.setattr(peer_compare, "_fetch_market_quotes", fake_quotes)
    monkeypatch.setattr(StockPriceCrawler, "_fetch_yfinance", lambda self, *a, **kw: pd.DataFrame())

    first = run(peer_compare.build_comparison("2330"))
    assert first["symbol"] == "2330" and len(first["peers"]) == 1

    # 清空程序內快取後重查：應在進入 _stock_info_maps 之前直接命中 Mongo 整包快取（0 次 FinMind）
    _clear_cache()
    fetch_log.clear()
    second = run(peer_compare.build_comparison("2330"))
    assert second["symbol"] == "2330"
    assert fetch_log == []


def test_screener_two_stage_prescreen_eliminates_without_finmind_and_skips_mktcap(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)
    today = date.today()
    today_s = today.isoformat()

    # 3 檔候選股：
    # - 1101：od_valuation PE=35（> 20）→ 第一階段直接淘汰（0 次 FinMind）
    # - 2330：od_valuation PE=16（<= 20）＋ od_revenue 近 3 月 YoY=25%（>= 10%）→ 進第二階段且命中
    # - 2317：od_valuation PE=12（<= 20）＋ od_revenue 近 3 月 YoY=2%（< 10%）→ 第一階段直接淘汰（0 次 FinMind）
    # - 3008：本地庫完全無資料 → 保留進第二階段補查（不漏召回）
    for sym, pe in (("1101", 35.0), ("2330", 16.0), ("2317", 12.0)):
        db["od_valuation"].docs.append({"mkt": "twse", "symbol": sym, "date": today_s, "pe": pe, "pb": 2.0, "dy": 3.0})

    # 種近 4 個月 od_revenue（涵蓋預期最新月份）
    rev_months = []
    for delta in (-4, -3, -2, -1):
        y, m = dr._shift_month(today.year, today.month, delta)
        rev_months.append(f"{y:04d}-{m:02d}")
    for ym in rev_months:
        db["od_revenue"].docs.append({"mkt": "twse", "symbol": "2330", "ym": ym, "rev": 1_000_000, "yoy": 25.0})
        db["od_revenue"].docs.append({"mkt": "twse", "symbol": "2317", "ym": ym, "rev": 1_000_000, "yoy": 2.0})

    async def fake_parse(query: str):
        return {
            "industry_keywords": [],
            "candidate_symbols": ["1101", "2330", "2317", "3008"],
            "pe_max": 20.0,
            "pe_min": None,
            "revenue_yoy_min": 10.0,
            "description": "PE<=20 且營收年增>=10%",
        }

    async def fake_info_maps():
        return (
            {"1101": "水泥", "2330": "半導體", "2317": "電子", "3008": "光電"},
            {"1101": "台泥", "2330": "台積電", "2317": "鴻海", "3008": "大立光"},
        )

    async def fake_quotes():
        return {"1101": 1e9, "2330": 9e9, "2317": 5e9, "3008": 3e9}

    stage2_called_syms = []
    finmind_calls = []

    async def fake_fetch(self, dataset, params):
        sym = params.get("data_id")
        finmind_calls.append((dataset, sym))
        if dataset == "TaiwanStockPrice":
            return pd.DataFrame([{"date": today_s, "open": 100, "max": 105, "min": 95, "close": 102, "Trading_Volume": 5000}])
        if dataset == "TaiwanStockPER":
            pe_val = 16.0 if sym == "2330" else 14.0
            return pd.DataFrame([{"date": today_s, "stock_id": sym, "PER": pe_val, "PBR": 2.5, "dividend_yield": 3.0}])
        if dataset == "TaiwanStockMonthRevenue":
            y = today.year
            return pd.DataFrame([
                {"date": f"{y - 1}-09-01", "revenue_year": y - 1, "revenue_month": 8, "revenue": 100},
                {"date": f"{y}-09-01", "revenue_year": y, "revenue_month": 8, "revenue": 130},
            ])
        if dataset == "TaiwanStockFinancialStatements":
            return pd.DataFrame([
                {"date": f"{today.year}-06-30", "type": "Revenue", "value": 1000},
                {"date": f"{today.year}-06-30", "type": "GrossProfit", "value": 500},
            ])
        return pd.DataFrame()

    orig_one = peer_compare._one_metrics

    async def spy_one(sym, name, source, **kwargs):
        stage2_called_syms.append((sym, kwargs.get("include_market_cap")))
        return await orig_one(sym, name, source, **kwargs)

    monkeypatch.setattr(nl_screener, "parse_query", fake_parse)
    monkeypatch.setattr(peer_compare, "_stock_info_maps", fake_info_maps)
    monkeypatch.setattr(peer_compare, "_fetch_market_quotes", fake_quotes)
    monkeypatch.setattr(peer_compare, "_one_metrics", spy_one)
    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)

    res = run(nl_screener.run_screener("找本益比小於20且營收年增大於10%"))

    # Schema 與候選池大小維持 100% 相容
    assert res["candidate_pool_size"] == 4
    assert res["matched_count"] == 2
    assert {r["symbol"] for r in res["matched"]} == {"2330", "3008"}

    # 1101（PE 不符）與 2317（YoY 不符）在第一階段即被淘汰，未進第二階段
    called_syms = {s for s, _ in stage2_called_syms}
    assert called_syms == {"2330", "3008"}
    assert "1101" not in called_syms and "2317" not in called_syms
    # 第二階段全部關閉市值查詢，絕不呼叫 TaiwanStockShareholding
    assert all(inc_cap is False for _, inc_cap in stage2_called_syms)
    assert all(ds != "TaiwanStockShareholding" for ds, _ in finmind_calls)


# ───────────────────────── 3. P0-2: 關聯圖不抓融資、滑桿零重抓、DB-first、熔斷與防污染 ─────────────────────────

def test_watch_graph_ingest_never_fetches_margin(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    datasets_called = []

    async def fake_fetch(self, dataset, params):
        datasets_called.append(dataset)
        if dataset == "TaiwanStockInfo":
            return pd.DataFrame([
                {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業"},
                {"stock_id": "2317", "stock_name": "鴻海", "industry_category": "其他電子業"},
            ])
        if dataset == "TaiwanStockPrice":
            return pd.DataFrame([
                {"date": "2026-11-10", "open": 100, "max": 102, "min": 99, "close": 101, "Trading_Volume": 1000},
                {"date": "2026-11-11", "open": 101, "max": 103, "min": 100, "close": 102, "Trading_Volume": 1200},
            ])
        if dataset == "TaiwanStockInstitutionalInvestorsBuySell":
            return pd.DataFrame([
                {"date": "2026-11-10", "name": "Foreign_Investor", "buy": 5000, "sell": 2000},
                {"date": "2026-11-11", "name": "Foreign_Investor", "buy": 6000, "sell": 1000},
            ])
        raise AssertionError(f"不應呼叫未預期的資料集：{dataset}")

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)

    res = run(watch_graph.ingest_watchlist_raw(["2330", "2317"], "2026-11-01", "2026-11-12"))
    assert res["prices"] == 4 and res["institutional"] == 4 and res["aborted"] is None
    assert "TaiwanStockMarginPurchaseShortSale" not in datasets_called


def test_watch_graph_timeline_reads_md_without_finmind_and_slider_hits_memcache(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)
    today = date.today()
    start_hist = today - timedelta(days=200)
    for sym, phase in (("2330", 0), ("2317", 2)):
        _seed_md_price(db, sym, start_hist, today, base=100.0, slope=0.4 if sym == "2330" else 0.3)
        _seed_md_institutional(db, sym, start_hist, today, phase=phase)
        db.raw_industry.docs.append({"symbol": sym, "name_zh": sym, "industry": "電子"})

    async def forbid_fetch(self, dataset, params):
        raise AssertionError(f"DB 已涵蓋時不應呼叫 FinMind：{dataset}")

    monkeypatch.setattr(FinMindClient, "_fetch", forbid_fetch)

    timeline_calls = []
    orig_timeline = graph_api.get_watchlist_timeline

    async def spy_timeline(*args, **kwargs):
        timeline_calls.append(kwargs.get("edge_threshold"))
        return await orig_timeline(*args, **kwargs)

    monkeypatch.setattr(graph_api, "get_watchlist_timeline", spy_timeline)

    app = FastAPI()
    app.include_router(graph_api.router)
    http = TestClient(app)

    s_day = (today - timedelta(days=3)).isoformat()
    e_day = today.isoformat()

    # 1. 首次載入：從 md_price + md_institutional 出圖，0 次 FinMind
    r1 = http.get(f"/api/v1/graph/watchlist/timeline?symbols=2330,2317&start={s_day}&end={e_day}&edge_threshold=0.05")
    assert r1.status_code == 200
    d1 = r1.json()["data"]
    assert len(d1["items"]) >= 1
    assert len(timeline_calls) == 1

    # 2. 拉動 Edge 門檻滑桿（0.05 → 0.50 → 0.99）且對調代碼順序（2317,2330）：全程命中 memcache，不再進 get_watchlist_timeline
    r2 = http.get(f"/api/v1/graph/watchlist/timeline?symbols=2317,2330&start={s_day}&end={e_day}&edge_threshold=0.50")
    r3 = http.get(f"/api/v1/graph/watchlist/timeline?symbols=2330,2317&start={s_day}&end={e_day}&edge_threshold=0.99")
    assert r2.status_code == 200 and r3.status_code == 200
    assert len(timeline_calls) == 1  # 完全沒重算、沒打 DB、沒打 FinMind！
    edges_low = len(d1["items"][-1]["layers"]["fusion"])
    edges_high = len(r3.json()["data"]["items"][-1]["layers"]["fusion"])
    assert edges_high <= edges_low


def test_watch_graph_quota_error_circuit_breaker_and_no_snapshot_pollution(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    # 先快取 stock_info，讓迴圈實際進入逐檔抓取並於第一檔觸發 HTTP 429 額度錯誤
    called_symbols = []

    async def quota_fetch(self, dataset, params):
        if dataset == "TaiwanStockInfo":
            return pd.DataFrame([
                {"stock_id": s, "stock_name": s, "industry_category": "半導體"}
                for s in ("2330", "2317", "2454", "2308", "2382")
            ])
        called_symbols.append((dataset, params.get("data_id")))
        raise ValueError("FinMind request failed: HTTP 429")

    monkeypatch.setattr(FinMindClient, "_fetch", quota_fetch)
    monkeypatch.setattr(StockPriceCrawler, "_fetch_yfinance", lambda self, *a, **kw: pd.DataFrame())

    # 1. 5 檔觀察池在第 1 檔遇到 429 即熔斷停手，絕不繼續打後面 4 檔
    res = run(watch_graph.ingest_watchlist_raw(["2330", "2317", "2454", "2308", "2382"], "2026-10-01", "2026-11-12"))
    assert res["aborted"] == "quota"
    assert {sym for _, sym in called_symbols} == {"2330"}

    # 2. 全無可用價格時建圖：禁止寫入 graph_snapshots 污染快取，並標註 degraded=True
    snap = run(watch_graph.build_watchlist_graph(["2330", "2317"], "2026-11-12", force_ingest=False))
    assert snap.get("degraded") is True
    assert all(n["latest_close"] is None for n in snap["nodes"])
    assert len(db.graph_snapshots.docs) == 0


# ───────────────────────── 4. P1-1: 類股輪動 watchlist 輕量 ingest 與 md_price 直讀 ─────────────────────────

def test_rotation_watchlist_build_skips_institutional_and_margin(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    datasets_called = []

    async def fake_fetch(self, dataset, params):
        datasets_called.append((dataset, params.get("data_id")))
        if dataset == "TaiwanStockInfo":
            return pd.DataFrame([
                {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業"},
                {"stock_id": "2317", "stock_name": "鴻海", "industry_category": "其他電子業"},
            ])
        if dataset == "TaiwanStockPrice":
            return pd.DataFrame([
                {"date": "2026-11-10", "open": 100, "max": 101, "min": 99, "close": 100.5, "Trading_Volume": 2000},
                {"date": "2026-11-11", "open": 101, "max": 102, "min": 100, "close": 101.5, "Trading_Volume": 2200},
            ])
        raise AssertionError(f"輪動 watchlist 不應呼叫：{dataset}")

    monkeypatch.setattr(FinMindClient, "_fetch", fake_fetch)

    app = FastAPI()
    app.include_router(rotation_api.router)
    http = TestClient(app)

    resp = http.post(
        "/api/v1/rotation/build",
        json={"universe": "watchlist", "symbols": ["2330", "2317"], "end": "2026-11-12", "lookback_days": 90},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["universe"] == "watchlist" and body["prices"] == 4
    called_ds = {ds for ds, _ in datasets_called}
    assert "TaiwanStockInstitutionalInvestorsBuySell" not in called_ds
    assert "TaiwanStockMarginPurchaseShortSale" not in called_ds


def test_rotation_watchlist_reads_md_price_without_finmind(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)
    today = date.today()
    start_d = today - timedelta(days=180)
    _seed_md_price(db, "2330", start_d, today, base=500.0, slope=1.2)
    _seed_md_price(db, "2317", start_d, today, base=150.0, slope=0.3)
    db.raw_industry.docs.append({"symbol": "2330", "name_zh": "台積電", "industry": "半導體業"})
    db.raw_industry.docs.append({"symbol": "2317", "name_zh": "鴻海", "industry": "其他電子業"})

    async def forbid_fetch(self, dataset, params):
        raise AssertionError(f"md_price 已存在時不應打 FinMind：{dataset}")

    monkeypatch.setattr(FinMindClient, "_fetch", forbid_fetch)

    snap = run(
        sector_rotation.get_rotation_snapshot(
            universe="watchlist",
            freq="daily",
            target_date=today,
            symbols=["2330", "2317"],
            lookback_days=180,
        )
    )
    assert len(snap["points"]) == 2
    assert {p["id"] for p in snap["points"]} == {"半導體業", "其他電子業"}


def test_watch_graph_snapshot_slider_and_degraded_not_cached_in_memcache(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)
    today = date.today()
    start_hist = today - timedelta(days=200)
    for sym, phase in (("2330", 0), ("2317", 1)):
        _seed_md_price(db, sym, start_hist, today, base=100.0, slope=0.5)
        _seed_md_institutional(db, sym, start_hist, today, phase=phase)
        db.raw_industry.docs.append({"symbol": sym, "name_zh": sym, "industry": "電子"})

    async def forbid_fetch(self, dataset, params):
        raise AssertionError(f"DB 已涵蓋時不應呼叫 FinMind：{dataset}")

    monkeypatch.setattr(FinMindClient, "_fetch", forbid_fetch)

    snap_calls = []
    orig_snap = graph_api.get_watchlist_snapshot

    async def spy_snap(*args, **kwargs):
        snap_calls.append(kwargs.get("edge_threshold"))
        return await orig_snap(*args, **kwargs)

    monkeypatch.setattr(graph_api, "get_watchlist_snapshot", spy_snap)

    app = FastAPI()
    app.include_router(graph_api.router)
    http = TestClient(app)

    d_str = today.isoformat()
    r1 = http.get(f"/api/v1/graph/watchlist/snapshot?symbols=2330,2317&date={d_str}&edge_threshold=0.05")
    r2 = http.get(f"/api/v1/graph/watchlist/snapshot?symbols=2317,2330&date={d_str}&edge_threshold=0.80")
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(snap_calls) == 1  # 門檻改變與代碼換序皆命中 memcache

    # 空資料降級快照不應寫進 memcache（下次恢復時立刻重建）
    empty_db = FakeDB()
    _bind_db(monkeypatch, empty_db)
    monkeypatch.setattr(StockPriceCrawler, "_fetch_yfinance", lambda self, *a, **kw: pd.DataFrame())

    async def empty_fetch(self, dataset, params):
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", empty_fetch)
    snap_calls.clear()
    r_deg1 = http.get(f"/api/v1/graph/watchlist/snapshot?symbols=9998,9999&date={d_str}&edge_threshold=0.12")
    r_deg2 = http.get(f"/api/v1/graph/watchlist/snapshot?symbols=9998,9999&date={d_str}&edge_threshold=0.12")
    assert r_deg1.status_code == 200 and r_deg2.status_code == 200
    assert r_deg1.json()["data"].get("degraded") is True
    assert len(snap_calls) == 2  # 降級結果沒被快取鎖死
    assert len(empty_db.graph_snapshots.docs) == 0


def test_watch_graph_quota_abort_on_stock_info_and_institutional(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)

    # Case A: get_stock_info 直接遇到 402 → 立刻熔斷，0 次進入個股迴圈
    called = []

    async def info_quota_fetch(self, dataset, params):
        called.append((dataset, params.get("data_id")))
        raise ValueError("FinMind request failed: HTTP 402")

    monkeypatch.setattr(FinMindClient, "_fetch", info_quota_fetch)
    res_a = run(watch_graph.ingest_watchlist_raw(["2330", "2317", "2454"], "2026-10-01", "2026-11-12"))
    assert res_a["aborted"] == "quota"
    assert called == [("TaiwanStockInfo", None)]

    # Case B: 價格成功但法人在第 1 檔觸發 429 → 立刻熔斷，不碰第 2、3 檔
    _clear_cache()
    called.clear()

    async def inst_quota_fetch(self, dataset, params):
        called.append((dataset, params.get("data_id")))
        if dataset == "TaiwanStockInfo":
            return pd.DataFrame([{"stock_id": s, "stock_name": s, "industry_category": "電子"} for s in ("2330", "2317", "2454")])
        if dataset == "TaiwanStockPrice":
            return pd.DataFrame([{"date": "2026-11-12", "open": 100, "max": 101, "min": 99, "close": 100, "Trading_Volume": 1000}])
        if dataset == "TaiwanStockInstitutionalInvestorsBuySell":
            raise ValueError("FinMind API error: upper limit")
        return pd.DataFrame()

    monkeypatch.setattr(FinMindClient, "_fetch", inst_quota_fetch)
    res_b = run(watch_graph.ingest_watchlist_raw(["2330", "2317", "2454"], "2026-10-01", "2026-11-12"))
    assert res_b["aborted"] == "quota"
    sym_calls = {sym for ds, sym in called if ds != "TaiwanStockInfo"}
    assert sym_calls == {"2330"}


def test_screener_prescreen_uses_md_valuation_and_md_revenue_when_od_absent(monkeypatch):
    db = FakeDB()
    _bind_db(monkeypatch, db)
    today = date.today()
    today_s = today.isoformat()

    # od_* 為空，改種 md_valuation 與 md_revenue：
    # - 2330: PER=15, 近 3 月營收年增 +20% → 保留
    # - 2317: PER=40 → 第一階段直接淘汰
    # - 2454: PER=15, 近 3 月營收年增 -5% → 第一階段直接淘汰
    db["md_valuation"].docs.extend([
        {"symbol": "2330", "date": today_s, "PER": 15.0, "PBR": 2.0, "dividend_yield": 3.0},
        {"symbol": "2317", "date": today_s, "PER": 40.0, "PBR": 2.0, "dividend_yield": 3.0},
        {"symbol": "2454", "date": today_s, "PER": 15.0, "PBR": 2.0, "dividend_yield": 3.0},
    ])
    for delta in range(-15, 0):
        y, m = dr._shift_month(today.year, today.month, delta)
        fm_d = dr.ym_to_finmind_date(f"{y:04d}-{m:02d}")
        is_recent = delta >= -3
        db["md_revenue"].docs.append({"symbol": "2330", "date": fm_d, "revenue_year": y, "revenue_month": m, "revenue": 1200.0 if is_recent else 1000.0})
        db["md_revenue"].docs.append({"symbol": "2454", "date": fm_d, "revenue_year": y, "revenue_month": m, "revenue": 950.0 if is_recent else 1000.0})

    criteria = {"pe_max": 20.0, "pe_min": None, "revenue_yoy_min": 10.0}
    survivors = run(nl_screener._prescreen_candidates(["2330", "2317", "2454"], criteria, today=today))
    assert survivors == ["2330"]

