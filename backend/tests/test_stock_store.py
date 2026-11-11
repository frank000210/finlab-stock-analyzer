"""每日資料庫（app/data/stock_store.py）：增量起點、upsert 不重複、白名單、額度用完停止、錯誤隔離。
db 與抓取函式都用假的，不連 Mongo、不打 FinMind。"""

import asyncio
from datetime import date, datetime

import pandas as pd
import pytest

from app.data import stock_store as st

TODAY = date(2026, 11, 11)


# ───────────── 假的 Mongo ─────────────
class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=1):
        self.docs = sorted(self.docs, key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def skip(self, n):
        self.docs = self.docs[n:]
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        return [dict(d) for d in self.docs]


def _match(doc, flt):
    for k, v in flt.items():
        if isinstance(v, dict):
            if "$in" in v and doc.get(k) not in v["$in"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class FakeColl:
    def __init__(self):
        self.docs = []
        self.n = 0

    async def create_index(self, *a, **k):
        return None

    async def find_one(self, flt):
        return next((dict(d) for d in self.docs if _match(d, flt)), None)

    def find(self, flt=None, proj=None):
        return FakeCursor([d for d in self.docs if _match(d, flt or {})])

    async def insert_one(self, doc):
        self.n += 1
        self.docs.append({**doc, "_id": self.n})

    async def delete_many(self, flt):
        ids = flt["_id"]["$in"]
        self.docs = [d for d in self.docs if d["_id"] not in ids]

    async def count_documents(self, flt):
        return len([d for d in self.docs if _match(d, flt)])

    async def update_one(self, flt, upd, upsert=False):
        hit = next((d for d in self.docs if _match(d, flt)), None)
        if hit is None and upsert:
            hit = {}
            self.docs.append(hit)
        if hit is not None:
            hit.update(upd["$set"])

    async def bulk_write(self, ops, ordered=False):
        for op in ops:  # pymongo.UpdateOne：用它的 _filter / _doc
            await self.update_one(op._filter, op._doc, upsert=True)


class FakeDB:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, FakeColl())

    @property
    def settings(self):
        return self["settings"]


def price_df(dates):
    return pd.DataFrame({"date": pd.to_datetime(dates), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1000.0})


def make_fetchers(calls, frames=None, boom=None):
    """每個資料集一個假抓取函式；calls 收集 (dataset, symbol, start, end)。"""
    frames = frames or {}

    def mk(ds):
        async def f(symbol, start, end):
            calls.append((ds, symbol, start, end))
            if boom and boom(ds, symbol):
                raise boom(ds, symbol)
            return frames.get(ds, pd.DataFrame())
        return f

    return {ds: mk(ds) for ds in st.DATASETS}


# ───────────── 純函式 ─────────────
def test_normalize_symbols():
    assert st.normalize_symbols("2330, 0050  2330 00940b") == ["2330", "0050", "00940B"]
    assert st.normalize_symbols(["2330", " 2317 "]) == ["2330", "2317"]
    assert st.normalize_symbols(None) == []
    with pytest.raises(ValueError):
        st.normalize_symbols(["2330", "23"])
    with pytest.raises(ValueError):
        st.normalize_symbols(["bad symbol!"])
    with pytest.raises(ValueError):
        st.normalize_symbols([str(1000 + i) for i in range(st.MAX_SYMBOLS + 1)])


def test_plan_start():
    assert st.plan_start(None, TODAY, 400, 3) == "2025-10-07"            # 第一次：回補
    assert st.plan_start("2026-11-06", TODAY, 400, 3) == "2026-11-03"    # 之後：last_date 往前重疊 3 天
    assert st.plan_start("2026-11-30", TODAY, 400, 3) == "2026-11-11" or st.plan_start("2026-11-30", TODAY, 400, 3) <= TODAY.isoformat()
    assert st.plan_start("壞掉的日期", TODAY, 30, 3) == "2026-10-12"


def test_rows_to_docs_cleans_and_filters():
    now = datetime(2026, 11, 11)
    docs = st.rows_to_docs("margin", "2330", [
        {"date": pd.Timestamp("2026-11-10"), "stock_id": "2330", "MarginPurchaseBuy": float("nan"), "ShortSaleSell": 5},
        {"date": None, "stock_id": "2330", "MarginPurchaseBuy": 1},
    ], now)
    assert len(docs) == 1 and docs[0]["date"] == "2026-11-10" and docs[0]["MarginPurchaseBuy"] is None
    assert "stock_id" not in docs[0] and docs[0]["symbol"] == "2330"
    inst = st.rows_to_docs("institutional", "2330", [
        {"date": "2026-11-10", "name": "Foreign_Investor", "buy": 1, "sell": 2},
        {"date": "2026-11-10", "buy": 1, "sell": 2},  # 沒有 name 不能當唯一鍵
    ], now)
    assert [d["name"] for d in inst] == ["Foreign_Investor"]


def test_is_quota_error():
    assert st.is_quota_error(ValueError("FinMind request failed: HTTP 402"))
    assert st.is_quota_error(ValueError("FinMind API error: Requests reach the upper limit"))
    assert not st.is_quota_error(ValueError("FinMind API error: bad data_id"))


# ───────────── run_sync ─────────────
def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_first_run_backfills_then_incremental_without_duplicates():
    db = FakeDB()
    calls = []
    frames = {"price": price_df(["2026-11-06", "2026-11-09", "2026-11-10"])}
    s1 = run(st.run_sync(["2330"], datasets=["price"], db=db, fetchers=make_fetchers(calls, frames), today=TODAY, pause=0))
    assert s1["rows"] == 3 and calls[0][2] == "2025-10-07"  # 回補 400 天
    assert [d["date"] for d in db["md_price"].docs] == ["2026-11-06", "2026-11-09", "2026-11-10"]
    assert db["md_state"].docs[0]["last_date"] == "2026-11-10"

    # 隔天：多一天資料。起點是 last_date 往前 3 天；重疊的列不會變兩份
    calls.clear()
    frames["price"] = price_df(["2026-11-09", "2026-11-10", "2026-11-11"])
    s2 = run(st.run_sync(["2330"], datasets=["price"], db=db, fetchers=make_fetchers(calls, frames), today=TODAY, pause=0))
    assert calls[0][2] == "2026-11-07"
    assert len(db["md_price"].docs) == 4 and s2["rows"] == 3
    assert db["md_state"].docs[0]["last_date"] == "2026-11-11"


def test_no_data_keeps_state_and_whitelist_comes_from_db():
    db = FakeDB()
    run(st.set_whitelist(["2330", "0050"], db=db))
    calls = []
    s = run(st.run_sync(None, datasets=["price"], db=db, fetchers=make_fetchers(calls), today=TODAY, pause=0))  # 假日：沒資料
    assert s["symbols"] == 2 and s["rows"] == 0 and [c[1] for c in calls] == ["2330", "0050"]
    assert all(d["last_date"] is None for d in db["md_state"].docs)


def test_empty_whitelist_is_a_noop():
    db = FakeDB()
    s = run(st.run_sync(None, db=db, fetchers={}, today=TODAY, pause=0))
    assert s["symbols"] == 0 and "白名單" in s["note"] and s["aborted"] is None


def test_error_is_isolated_per_dataset_and_symbol():
    db = FakeDB()
    calls = []
    frames = {"price": price_df(["2026-11-10"])}
    boom = lambda ds, sym: ValueError("FinMind API error: bad data_id") if (ds, sym) == ("margin", "2330") else None  # noqa: E731
    s = run(st.run_sync(["2330", "2317"], datasets=["price", "margin"], db=db, fetchers=make_fetchers(calls, frames, boom), today=TODAY, pause=0))
    assert s["errors"] == 1 and s["aborted"] is None
    assert len(calls) == 4                                 # 一個失敗不影響其他
    assert s["per_symbol"]["2317"]["errors"] == 0
    bad = next(d for d in db["md_state"].docs if d["symbol"] == "2330" and d["dataset"] == "margin")
    assert bad["last_error"]


def test_quota_error_aborts_the_run_and_keeps_stored_data():
    db = FakeDB()
    calls = []
    frames = {"price": price_df(["2026-11-10"])}
    boom = lambda ds, sym: ValueError("FinMind request failed: HTTP 402") if sym == "2317" else None  # noqa: E731
    s = run(st.run_sync(["2330", "2317", "0050"], datasets=["price"], db=db, fetchers=make_fetchers(calls, frames, boom), today=TODAY, pause=0))
    assert s["aborted"] == "quota"
    assert [c[1] for c in calls] == ["2330", "2317"]       # 0050 沒有再打
    assert len(db["md_price"].docs) == 1                   # 2330 已存的還在


def test_second_run_is_skipped_while_one_is_running():
    db = FakeDB()

    async def scenario():
        gate = asyncio.Event()

        async def slow(symbol, start, end):
            await gate.wait()
            return pd.DataFrame()

        f = {ds: slow for ds in st.DATASETS}
        t1 = asyncio.create_task(st.run_sync(["2330"], datasets=["price"], db=db, fetchers=f, today=TODAY, pause=0))
        await asyncio.sleep(0.05)
        second = await st.run_sync(["2330"], db=db, fetchers=f, today=TODAY, pause=0)
        gate.set()
        await t1
        return second

    assert asyncio.new_event_loop().run_until_complete(scenario()) == {"skipped": "already_running"}
    assert st.is_running() is False


def test_status_reports_whitelist_counts_and_runs():
    db = FakeDB()
    run(st.set_whitelist(["2330"], db=db))
    run(st.run_sync(None, datasets=["price"], db=db, fetchers=make_fetchers([], {"price": price_df(["2026-11-10"])}), today=TODAY, pause=0))
    s = run(st.get_status(db=db))
    assert s["whitelist"] == {"symbols": ["2330"], "source": "db"}
    assert s["stored_counts"]["price"] == 1
    assert s["symbols"]["2330"]["price"]["last_date"] == "2026-11-10"
    assert s["recent_runs"][0]["rows"] == 1 and s["running"] is False
