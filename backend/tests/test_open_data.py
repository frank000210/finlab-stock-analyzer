"""官方開放資料倉庫（app/data/open_data.py）。

假的 Mongo＋httpx.MockTransport：不連資料庫、不碰網路。測試樣本的欄位名稱與格式取自 2026-11-12 實際抓到的回應。
重點：日期正確（證交所融資融券不能把昨天標成今天）、重跑不重複、被擋就停且冷卻、格式改版不寫入、
一個來源失敗不影響其他、健康判斷。
"""

import asyncio
import json
from dataclasses import replace
from datetime import date, datetime, timedelta

import httpx
import pytest

from app.data import open_data as od

TODAY = date(2026, 11, 12)  # 星期四
NOW = datetime(2026, 11, 12, 13, 30)  # naive UTC（= 台灣 21:30）


def run(coro):
    return asyncio.run(coro)


# ───────────── 假的 Mongo ─────────────
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
        elif have != v:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=1):
        self.docs = sorted(self.docs, key=lambda d: (d.get(key) is None, d.get(key)), reverse=direction < 0)
        return self

    def skip(self, n):
        self.docs = self.docs[n:]
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        return [dict(d) for d in self.docs]


class FakeColl:
    def __init__(self):
        self.docs = []
        self.n = 0

    async def create_index(self, *a, **k):
        return None

    async def find_one(self, flt):
        return next((dict(d) for d in self.docs if _match(d, flt)), None)

    def find(self, flt=None, proj=None):
        return FakeCursor([d for d in self.docs if _match(d, flt)])

    async def distinct(self, field, flt=None):
        return sorted({d[field] for d in self.docs if _match(d, flt) and field in d})

    async def insert_one(self, doc):
        self.n += 1
        self.docs.append({**doc, "_id": self.n})

    async def delete_many(self, flt):
        ids = flt["_id"]["$in"]
        self.docs = [d for d in self.docs if d["_id"] not in ids]

    async def count_documents(self, flt):
        return len([d for d in self.docs if _match(d, flt)])

    async def estimated_document_count(self):
        return len(self.docs)

    async def update_one(self, flt, upd, upsert=False):
        hit = next((d for d in self.docs if _match(d, flt)), None)
        if hit is None:
            if not upsert:
                return
            hit = {k: v for k, v in flt.items() if not isinstance(v, dict)}
            hit.update(upd.get("$setOnInsert", {}))
            self.docs.append(hit)
        hit.update(upd.get("$set", {}))

    async def bulk_write(self, ops, ordered=False):
        for op in ops:  # pymongo.UpdateOne：用它的 _filter / _doc
            await self.update_one(op._filter, op._doc, upsert=True)


class FakeDB:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, FakeColl())


# ───────────── 樣本資料（欄位與格式同官方）─────────────
TWSE_MARGIN_FIELDS = ["代號", "名稱", "買進", "賣出", "現金償還", "前日餘額", "今日餘額", "次一營業日限額",
                      "買進", "賣出", "現券償還", "前日餘額", "今日餘額", "次一營業日限額", "資券互抵", "註記"]


def twse_margin_payload(d, n=3):
    rows = [[f"{1101 + i}", f"股{i}", "671", "1,903", "113", "16,405", "15,060", "608,285", "0", "1", "0", "6", "7", "608,285", "74", " "] for i in range(n)]
    return {"stat": "OK", "date": d, "tables": [
        {"title": "信用交易統計", "fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"], "data": [["融資(交易單位)", "1", "2", "3", "4", "5"]]},
        {"title": "融資融券彙總 (全部)", "fields": TWSE_MARGIN_FIELDS, "data": rows},
    ]}


def tpex_margin_rows(n=3, d="1151112"):
    return [{"Date": d, "SecuritiesCompanyCode": f"{3105 + i}", "CompanyName": "穩懋", "MarginPurchaseBalancePreviousDay": "19841", "MarginPurchase": "514",
             "MarginSales": "743", "CashRedemption": "0", "MarginPurchaseBalance": "19612", "MarginPurchaseBalanceBelongSecuritiesFinanceEnterprise": "81",
             "MarginPurchaseUtilizationRate": "16.77", "MarginPurchaseQuota": "116894", "ShortSaleBalancePreviousDay": "2", "ShortSale": "0", "ShortConvering": "2",
             "StockRedemption": "0", "ShortSaleBalance": "0", "ShortSaleBalanceBelongSecuritiesFinanceEnterprise": "0", "ShortSaleUtilizationRate": "0.0",
             "ShortSaleQuota": "116894", "Offsetting": "0", "Note": ""} for i in range(n)]


def twse_valuation_rows(n=3, d="1151111"):
    return [{"Date": d, "Code": f"{1101 + i}", "Name": "台泥", "PEratio": "" if i == 0 else "10.38", "DividendYield": "2.89", "PBratio": "0.90"} for i in range(n)]


def tpex_valuation_rows(n=3, d="1151112"):
    return [{"Date": d, "SecuritiesCompanyCode": f"{1240 + i}", "CompanyName": "茂生農經", "PriceEarningRatio": "11.74", "DividendPerShare": "0.50000000", "YieldRatio": "0.93", "PriceBookRatio": "1.65"} for i in range(n)]


def revenue_rows(n=3, d="1151111", ym="11510", code0=1101):
    return [{"出表日期": d, "資料年月": ym, "公司代號": f"{code0 + i}", "公司名稱": "台泥", "產業別": "水泥工業", "營業收入-當月營收": "16357176", "營業收入-上月營收": "14321556",
             "營業收入-去年當月營收": "13882248", "營業收入-上月比較增減(%)": "14.213679016442068", "營業收入-去年同月增減(%)": "17.828005954078908",
             "累計營業收入-當月累計營收": "129405701", "累計營業收入-去年累計營收": "123320545", "累計營業收入-前期比較增減(%)": "4.934421916477907", "備註": "-"} for i in range(n)]


TWSE_PUNISH = [{"Number": "1", "Date": "1151106", "Code": "3532", "Name": "台勝科", "NumberOfAnnouncement": "1", "ReasonsOfDisposition": "連續三次",
                "DispositionPeriod": "115/11/09～115/11/13", "DispositionMeasures": "第一次處置", "Detail": "１處置原因：…", "LinkInformation": "…"}]
TPEX_DISPOSAL = [{"Date": "1151111", "SecuritiesCompanyCode": "54642", "CompanyName": "霖宏二", "DispositionPeriod": "1151112~1151118", "DispositionReasons": "連續3個營業日", "DisposalCondition": "* 公布日期：115/11/11"}]
TWSE_NOTICE_EMPTY = [{"Number": "0", "Code": "", "Name": "", "NumberOfAnnouncement": "0", "TradingInfoForAttention": "", "Date": "", "ClosingPrice": "0", "PE": "0"}]
TPEX_WARNING = [{"Date": "1151112", "SecuritiesCompanyCode": "3105", "CompanyName": "穩懋", "TradingInformation": "最近六個營業日…（第十三款)", "ClosePrice": "517.00", "PriceEarningRatio": "49.05"}]


def tdcc_csv(symbols=("2330", "0050"), d="20261106"):
    lines = ["資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%"]
    for s in symbols:
        total_h = total_s = 0
        for lvl in range(1, 16):
            h, sh, pct = (10 * lvl, 1000 * lvl, 1.0) if lvl < 12 else (2, 500_000 * (lvl - 10), 10.0 + lvl)
            total_h += h
            total_s += sh
            lines.append(f"{d},{s},{lvl},{h},{sh},{pct:.2f}")
        lines.append(f"{d},{s},16,0,0,0.00")
        lines.append(f"{d},{s},17,{total_h},{total_s},100.00")
    return "\n".join(lines) + "\n"


# ───────────── 假的來源（httpx.MockTransport）─────────────
class Site:
    """依路徑回應；記錄每個請求。overrides 可針對路徑改回應（status 或自訂函式）。"""

    def __init__(self, margin_dates=("20261109", "20261110", "20261111", "20261112"), n=3):
        self.n, self.margin_dates, self.log, self.override = n, set(margin_dates), [], {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, dict(request.url.params)
        self.log.append((request.url.host, path, q))
        if path in self.override:
            o = self.override[path]
            return o(request) if callable(o) else httpx.Response(o)
        n = self.n
        if path == "/rwd/zh/marginTrading/MI_MARGN":
            d = q["date"]
            if d in self.margin_dates:
                return httpx.Response(200, json=twse_margin_payload(d, n))
            return httpx.Response(200, json={"stat": "很抱歉，沒有符合條件的資料"})
        routes = {
            "/openapi/v1/tpex_mainboard_margin_balance": tpex_margin_rows(n),
            "/v1/exchangeReport/BWIBBU_ALL": twse_valuation_rows(n),
            "/openapi/v1/tpex_mainboard_peratio_analysis": tpex_valuation_rows(n),
            "/v1/opendata/t187ap05_L": revenue_rows(n),
            "/openapi/v1/mopsfin_t187ap05_O": revenue_rows(n, d="1151112", code0=1240),
            "/v1/announcement/punish": TWSE_PUNISH,
            "/openapi/v1/tpex_disposal_information": TPEX_DISPOSAL,
            "/v1/announcement/notice": TWSE_NOTICE_EMPTY,
            "/openapi/v1/tpex_trading_warning_information": TPEX_WARNING,
        }
        if path in routes:
            return httpx.Response(200, json=routes[path])
        if path == "/getOD.ashx":
            return httpx.Response(200, content=("﻿" + tdcc_csv()).encode("utf-8"))
        return httpx.Response(404)

    def count(self, path):
        return len([x for x in self.log if x[1] == path])


class Clock:
    """假時鐘＋假 sleep：記錄睡了多久，不真的等。"""

    def __init__(self):
        self.t, self.sleeps = 100.0, []

    def __call__(self):
        return self.t

    async def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def make_client(site, clock=None, **kw):
    clock = clock or Clock()
    return od.OpenDataClient(transport=httpx.MockTransport(site.handler), sleep=clock.sleep, clock=clock, **kw), clock


@pytest.fixture(autouse=True)
def small_min_rows(monkeypatch):
    """樣本只有 2～3 筆；把「至少幾筆」的門檻降到 2，門檻本身另有測試。"""
    monkeypatch.setattr(od, "SOURCES", [replace(s, min_rows=min(s.min_rows, 2)) for s in od.SOURCES])
    monkeypatch.setattr(od, "_running", False)


def sync(db, site=None, **kw):
    site = site or Site()
    client, _ = make_client(site)
    kw.setdefault("now", NOW)
    kw.setdefault("today", TODAY)
    kw.setdefault("trigger", "test")
    res = run(od.run_sync(db=db, client=client, **kw))
    run(client.aclose())
    return res, site


# ───────────── 日期與數字 ─────────────
def test_roc_to_iso_handles_all_formats():
    assert od.roc_to_iso("1151112") == "2026-11-12"      # 民國 7 碼
    assert od.roc_to_iso("115/11/09") == "2026-11-09"    # 民國含斜線
    assert od.roc_to_iso("20261106") == "2026-11-06"     # 集保西元
    assert od.roc_to_iso("2026-11-12") == "2026-11-12"
    assert od.roc_to_iso("991231") == "2010-12-31"       # 民國 99 年（6 碼）
    for bad in (None, "", "abc", "1151332", "20261301", "123"):
        assert od.roc_to_iso(bad) is None


def test_roc_ym():
    assert od.roc_ym("11510") == "2026-10"
    assert od.roc_ym("202610") == "2026-10"
    assert od.roc_ym("11513") is None and od.roc_ym("") is None and od.roc_ym(None) is None


def test_to_num():
    assert od.to_num("1,234") == 1234 and isinstance(od.to_num("1,234"), int)
    assert od.to_num("10.38") == 10.38
    assert od.to_num("0.00") == 0 and od.to_num("0") == 0
    assert od.to_num("466", integer=True) == 466
    assert od.to_num("-16.7") == -16.7
    for empty in ("", " ", "-", "--", "N/A", None, "abc", "nan", float("nan"), float("inf")):
        assert od.to_num(empty) is None


def test_clean_symbol():
    assert od.clean_symbol(" 00400a ") == "00400A"
    assert od.clean_symbol("2330") == "2330"
    assert od.clean_symbol("") is None and od.clean_symbol(None) is None and od.clean_symbol("bad symbol!") is None


def test_recent_weekdays_skips_weekend():
    assert od.recent_weekdays(date(2026, 11, 12), 5) == [date(2026, 11, d) for d in (6, 9, 10, 11, 12)]
    assert od.recent_weekdays(date(2026, 11, 15), 2) == [date(2026, 11, 12), date(2026, 11, 13)]  # 週日起算


# ───────────── 解析 ─────────────
def test_parse_twse_margin_uses_payload_date_and_positions():
    d, docs = od.parse_twse_margin(twse_margin_payload("20261112", 2))
    assert d == "2026-11-12" and len(docs) == 2
    x = docs[0]
    assert (x["mkt"], x["symbol"], x["date"]) == ("twse", "1101", "2026-11-12")
    assert (x["margin_buy"], x["margin_sell"], x["margin_repay"]) == (671, 1903, 113)   # 逗號被去掉
    assert (x["margin_prev"], x["margin_bal"], x["margin_limit"]) == (16405, 15060, 608285)
    assert (x["short_cover"], x["short_sell"], x["short_repay"]) == (0, 1, 0)
    assert (x["short_prev"], x["short_bal"], x["short_limit"], x["offset"]) == (6, 7, 608285, 74)


def test_parse_twse_margin_rejects_changed_layout():
    p = twse_margin_payload("20261112")
    p["tables"][1]["fields"] = p["tables"][1]["fields"][:-1]  # 少一欄
    with pytest.raises(od.SchemaError, match="彙總"):
        od.parse_twse_margin(p)
    with pytest.raises(od.SchemaError, match="日期"):
        od.parse_twse_margin({"stat": "OK", "tables": []})


def test_parse_tpex_margin_maps_fields():
    docs = od.parse_tpex_margin(tpex_margin_rows(1))
    x = docs[0]
    assert (x["mkt"], x["symbol"], x["date"]) == ("tpex", "3105", "2026-11-12")
    assert (x["margin_prev"], x["margin_buy"], x["margin_sell"], x["margin_bal"], x["margin_limit"]) == (19841, 514, 743, 19612, 116894)
    assert (x["short_prev"], x["short_cover"], x["short_sell"], x["short_bal"]) == (2, 2, 0, 0)
    assert set(x) == set(od.parse_twse_margin(twse_margin_payload("20261112", 1))[1][0])  # 上市／上櫃欄位一致，才能一起查


def test_parse_valuation_handles_missing_pe():
    tw = od.parse_twse_valuation(twse_valuation_rows(2))
    assert tw[0]["pe"] is None and tw[0]["pb"] == 0.9 and tw[0]["dy"] == 2.89 and tw[1]["pe"] == 10.38
    tp = od.parse_tpex_valuation(tpex_valuation_rows(1))
    assert (tp[0]["pe"], tp[0]["pb"], tp[0]["dy"], tp[0]["dps"], tp[0]["date"]) == (11.74, 1.65, 0.93, 0.5, "2026-11-12")


def test_parse_revenue():
    docs = od.parse_twse_revenue(revenue_rows(1))
    x = docs[0]
    assert (x["symbol"], x["ym"], x["report_date"], x["industry"]) == ("1101", "2026-10", "2026-11-11", "水泥工業")
    assert (x["rev"], x["rev_prev_month"], x["rev_prev_year"], x["cum"]) == (16357176, 14321556, 13882248, 129405701)
    assert x["yoy"] == pytest.approx(17.828, abs=1e-3) and x["note"] is None  # 備註 "-" 視為沒有


def test_parse_disposal_period_formats():
    tw = od.parse_twse_disposal(TWSE_PUNISH)[0]
    assert (tw["symbol"], tw["date"], tw["start"], tw["end"], tw["times"]) == ("3532", "2026-11-06", "2026-11-09", "2026-11-13", 1)
    tp = od.parse_tpex_disposal(TPEX_DISPOSAL)[0]
    assert (tp["symbol"], tp["date"], tp["start"], tp["end"]) == ("54642", "2026-11-11", "2026-11-12", "2026-11-18")


def test_parse_attention_drops_empty_placeholder_row():
    assert od.parse_twse_attention(TWSE_NOTICE_EMPTY) == []   # 當天沒有注意股時來源回一列空白假資料
    tp = od.parse_tpex_attention(TPEX_WARNING)[0]
    assert (tp["symbol"], tp["date"], tp["close"], tp["pe"]) == ("3105", "2026-11-12", 517.0, 49.05)


def test_parse_missing_fields_raise_schema_error():
    rows = twse_valuation_rows(2)
    for r in rows:
        r.pop("PBratio")
    with pytest.raises(od.SchemaError, match="PBratio"):
        od.parse_twse_valuation(rows)
    assert od.parse_twse_valuation([]) == []   # 空清單不是格式錯誤（例如當天沒有處置股）


def test_parse_tdcc_groups_17_levels_into_one_doc_per_stock():
    docs = od.parse_tdcc(tdcc_csv(("2330", "0050")))
    assert len(docs) == 2
    x = next(d for d in docs if d["symbol"] == "2330")
    assert x["date"] == "2026-11-06" and len(x["lv"]) == 15
    assert x["lv"][0] == [10, 1000, 1.0] and x["lv"][14] == [2, 2_500_000, 25.0]
    assert x["pct_1000plus"] == 25.0 and x["holders_1000plus"] == 2
    assert x["pct_400plus"] == pytest.approx(sum(10.0 + lvl for lvl in (12, 13, 14, 15)))  # 第 12～15 級
    assert x["holders_400plus"] == 8 and x["total_holders"] > 0 and x["total_shares"] > 0 and x["adj_shares"] == 0


def test_parse_tdcc_rejects_unexpected_header_and_skips_bad_rows():
    with pytest.raises(od.SchemaError, match="表頭"):
        od.parse_tdcc("a,b,c\n1,2,3\n")
    docs = od.parse_tdcc("資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%\n20261106,2330,1,1,1,0.5\n壞,,x,1,1,1\n20261106,2330,99,1,1,1\n")
    assert len(docs) == 1 and docs[0]["lv"][0] == [1, 1, 0.5]


def test_check_volume_blocks_suspiciously_small_or_unparsed_results():
    src = od.Source("x", "margin", "twse", "u", "json", 800)
    with pytest.raises(od.SchemaError, match="至少應有 800"):
        od.check_volume(src, 100, [{}] * 100)
    src0 = od.Source("y", "disposal", "twse", "u", "json", 0)
    od.check_volume(src0, 0, [])   # 允許空
    with pytest.raises(od.SchemaError, match="解析出"):   # 欄位改名：原始 500 筆、幾乎都解析不出來
        od.check_volume(src0, 500, [{}] * 10)


# ───────────── HTTP 客戶端 ─────────────
def test_client_sends_honest_user_agent_and_spaces_requests():
    seen = []

    def handler(req):
        seen.append(req.headers["user-agent"])
        return httpx.Response(200, json=[])

    clock = Clock()
    client = od.OpenDataClient(transport=httpx.MockTransport(handler), sleep=clock.sleep, clock=clock)
    run(client.get_json("https://example.test/a"))
    run(client.get_json("https://example.test/b"))
    assert seen[0] == od.UA and "python" not in od.UA.lower() and "finlab" in od.UA
    assert clock.sleeps and clock.sleeps[0] == pytest.approx(od.MIN_GAP_SEC)   # 第二個請求等滿 1 秒（第一個不用等）


@pytest.mark.parametrize("status", [403, 429])
def test_client_blocked_stops_immediately_without_retry(status):
    site = Site()
    site.override["/x"] = status
    client, _ = make_client(site)
    with pytest.raises(od.BlockedError):
        run(client.get("https://example.test/x"))
    assert site.count("/x") == 1


def test_client_firewall_page_is_blocked_even_with_200():
    site = Site()
    site.override["/x"] = lambda r: httpx.Response(200, text="<html>FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED!</html>")
    client, _ = make_client(site)
    with pytest.raises(od.BlockedError):
        run(client.get_json("https://example.test/x"))


def test_client_does_not_follow_redirect_and_reports_moved_endpoint():
    site = Site()
    site.override["/old"] = lambda r: httpx.Response(302, headers={"location": "https://example.test/new"})
    client, _ = make_client(site)
    with pytest.raises(od.FetchError, match="轉到.*改版"):
        run(client.get("https://example.test/old"))
    assert site.count("/old") == 1 and site.count("/new") == 0


def test_client_404_means_outdated_url():
    site = Site()
    client, _ = make_client(site)
    with pytest.raises(od.FetchError, match="404.*改版"):
        run(client.get("https://example.test/gone"))


def test_client_retries_5xx_twice_then_gives_up_with_backoff():
    site = Site()
    site.override["/flaky"] = 503
    client, clock = make_client(site)
    with pytest.raises(od.FetchError, match="503"):
        run(client.get("https://example.test/flaky"))
    assert site.count("/flaky") == 1 + od.RETRIES
    assert od.RETRY_BACKOFF_SEC in clock.sleeps


def test_client_recovers_after_transient_failure():
    site = Site()
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        return httpx.Response(500) if calls["n"] == 1 else httpx.Response(200, json=[1])

    site.override["/f"] = flaky
    client, _ = make_client(site)
    assert run(client.get_json("https://example.test/f")) == [1]


def test_client_non_json_is_schema_error():
    site = Site()
    site.override["/h"] = lambda r: httpx.Response(200, text="<html>維護中</html>")
    client, _ = make_client(site)
    with pytest.raises(od.SchemaError, match="不是 JSON"):
        run(client.get_json("https://example.test/h"))


# ───────────── 證交所融資融券（逐日、帶日期）─────────────
def test_twse_margin_fetches_each_missing_weekday_and_records_holiday():
    site = Site()
    client, _ = make_client(site)
    src = next(s for s in od.SOURCES if s.name == "twse_margin")
    res = run(od.pull_twse_margin(client, src, TODAY, known_dates=set(), prev_empty=[]))
    assert {d["date"] for d in res.docs} == {"2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"}
    assert res.empty_dates == ["2026-11-06"]   # 11/06 回「沒有符合條件」→ 過去的日子記起來
    assert res.data_date == "2026-11-12"
    assert [x[2]["date"] for x in site.log] == ["20261106", "20261109", "20261110", "20261111", "20261112"]


def test_twse_margin_skips_known_and_empty_dates():
    site = Site()
    client, _ = make_client(site)
    src = next(s for s in od.SOURCES if s.name == "twse_margin")
    res = run(od.pull_twse_margin(client, src, TODAY, known_dates={"2026-11-09", "2026-11-10", "2026-11-11"}, prev_empty=["2026-11-06"]))
    assert [x[2]["date"] for x in site.log] == ["20261112"]
    assert {d["date"] for d in res.docs} == {"2026-11-12"}


def test_twse_margin_today_not_yet_published_is_retried_tomorrow_not_recorded_as_empty():
    site = Site(margin_dates=("20261109", "20261110", "20261111"))   # 今天 11/12 的資料還沒出
    client, _ = make_client(site)
    src = next(s for s in od.SOURCES if s.name == "twse_margin")
    res = run(od.pull_twse_margin(client, src, TODAY, set(), []))
    assert "2026-11-12" not in (res.empty_dates or []) and res.data_date == "2026-11-11"


def test_twse_margin_rejects_response_for_a_different_date():
    site = Site()
    site.override["/rwd/zh/marginTrading/MI_MARGN"] = lambda r: httpx.Response(200, json=twse_margin_payload("20261111", 3))
    client, _ = make_client(site)
    src = next(s for s in od.SOURCES if s.name == "twse_margin")
    with pytest.raises(od.SchemaError, match="要求"):
        run(od.pull_twse_margin(client, src, TODAY, set(), []))


def test_twse_margin_rate_limit_message_is_treated_as_blocked():
    site = Site()
    site.override["/rwd/zh/marginTrading/MI_MARGN"] = lambda r: httpx.Response(200, json={"stat": "查詢過於頻繁，請稍後再試"})
    client, _ = make_client(site)
    src = next(s for s in od.SOURCES if s.name == "twse_margin")
    with pytest.raises(od.BlockedError):
        run(od.pull_twse_margin(client, src, TODAY, set(), []))


# ───────────── 整輪（假資料庫＋假來源）─────────────
def test_run_stores_every_dataset_with_correct_dates():
    db = FakeDB()
    res, site = sync(db)
    assert res["aborted"] is None and res["errors"] == 0
    margin = db["od_margin"].docs
    assert {(d["mkt"], d["date"]) for d in margin} == {("twse", "2026-11-09"), ("twse", "2026-11-10"), ("twse", "2026-11-11"), ("twse", "2026-11-12"), ("tpex", "2026-11-12")}
    assert len(margin) == 4 * 3 + 3
    assert {d["date"] for d in db["od_valuation"].docs} == {"2026-11-11", "2026-11-12"}   # 上市 11/11、上櫃 11/12：各自的日期，不混
    assert {d["ym"] for d in db["od_revenue"].docs} == {"2026-10"}
    assert len(db["od_disposal"].docs) == 2 and db["od_attention"].docs[0]["symbol"] == "3105"
    assert len(db["od_tdcc"].docs) == 2 and db["od_tdcc"].docs[0]["date"] == "2026-11-06"
    st = db["od_state"]
    assert {d["_id"] for d in st.docs} == set(od.DATASETS)
    assert next(d for d in st.docs if d["_id"] == "margin")["last_data_date"] == "2026-11-12"
    assert next(d for d in st.docs if d["_id"] == "valuation")["last_data_date"] == "2026-11-12"
    assert len(db["od_runs"].docs) == 1 and res["requests"] == len(site.log)


def test_second_run_is_idempotent_and_asks_for_less():
    db = FakeDB()
    sync(db)
    before = {k: len(v.docs) for k, v in db.colls.items()}
    first = next(d for d in db["od_revenue"].docs if d["symbol"] == "1101")["first_seen"]
    res2, site2 = sync(db, now=NOW + timedelta(hours=1))
    assert {k: len(v.docs) for k, v in db.colls.items() if k != "od_runs"} == {k: n for k, n in before.items() if k != "od_runs"}   # 沒有重複文件
    assert next(d for d in db["od_revenue"].docs if d["symbol"] == "1101")["first_seen"] == first
    assert site2.count("/rwd/zh/marginTrading/MI_MARGN") == 0       # 四天都存過、11/06 已知是假日 → 融資融券一個請求都不用
    assert site2.count("/getOD.ashx") == 0                          # 集保已有 7 天內的最新一份
    assert len(db["od_runs"].docs) == 2


def test_first_seen_is_set_on_insert_only():
    db = FakeDB()
    sync(db, today=TODAY)
    sync(db, today=TODAY + timedelta(days=1), now=NOW + timedelta(days=1), site=Site(margin_dates=("20261109", "20261110", "20261111", "20261112", "20261113")))
    rev = next(d for d in db["od_revenue"].docs if d["symbol"] == "1101")
    assert rev["first_seen"] == "2026-11-12"   # 第二天又抓到同一份月營收，仍記第一次看到的日子（回測不能偷看未來）


def test_failed_source_does_not_stop_others_and_dataset_is_not_marked_fresh():
    db = FakeDB()
    site = Site()
    site.override["/openapi/v1/tpex_mainboard_margin_balance"] = 500
    res, _ = sync(db, site=site)
    assert res["errors"] == 1 and res["aborted"] is None
    assert res["sources"]["tpex_margin"]["error"] and not res["sources"]["tpex_margin"]["ok"]
    assert len(db["od_margin"].docs) == 12                       # 上市仍然寫進去了
    assert len(db["od_valuation"].docs) == 6 and len(db["od_tdcc"].docs) == 2   # 其他資料集不受影響
    st = next(d for d in db["od_state"].docs if d["_id"] == "margin")
    assert st["last_success_at"] is None and "tpex_margin" in st["last_error"]   # 少了半個市場，不能算成功


def test_schema_drift_writes_nothing_for_that_source_only():
    db = FakeDB()
    site = Site()

    def drifted(req):
        rows = twse_valuation_rows(5)
        for r in rows:
            r["PBR"] = r.pop("PBratio")   # 欄位改名
        return httpx.Response(200, json=rows)

    site.override["/v1/exchangeReport/BWIBBU_ALL"] = drifted
    res, _ = sync(db, site=site)
    assert "欄位不見了" in res["sources"]["twse_valuation"]["error"]
    assert {d["mkt"] for d in db["od_valuation"].docs} == {"tpex"}   # 壞掉的來源一筆都沒寫
    assert len(db["od_margin"].docs) > 0


def test_too_few_rows_is_rejected_not_written(monkeypatch):
    monkeypatch.setattr(od, "SOURCES", [replace(s, min_rows=10) if s.name == "twse_valuation" else s for s in od.SOURCES])
    db = FakeDB()
    res, _ = sync(db)
    assert "至少應有 10" in res["sources"]["twse_valuation"]["error"]
    assert {d["mkt"] for d in db["od_valuation"].docs} == {"tpex"}


def test_blocked_aborts_whole_run_and_cools_off():
    db = FakeDB()
    site = Site()
    site.override["/v1/exchangeReport/BWIBBU_ALL"] = 403
    res, _ = sync(db, site=site)
    assert res["aborted"] == "blocked" and res["errors"] >= 1
    assert site.count("/v1/opendata/t187ap05_L") == 0 and site.count("/getOD.ashx") == 0      # 後面的資料集一個請求都沒發
    assert len(db["od_margin"].docs) > 0                                                      # 被擋之前存好的保留
    meta = next(d for d in db["od_state"].docs if d["_id"] == od.META_ID)
    assert meta["blocked_until"] == NOW + timedelta(hours=od.COOL_OFF_HOURS)
    val = next(d for d in db["od_state"].docs if d["_id"] == "valuation")
    assert "被擋" in val["last_error"] and val["last_success_at"] is None

    # 冷卻中：再跑也不會發出任何請求（包含手動觸發）
    site2 = Site()
    res2, _ = sync(db, site=site2, now=NOW + timedelta(hours=1), trigger="manual", force=True)
    assert res2["skipped"] == "cooling_off" and site2.log == []

    # 冷卻結束後恢復
    site3 = Site()
    res3, _ = sync(db, site=site3, now=NOW + timedelta(hours=od.COOL_OFF_HOURS, minutes=1))
    assert res3["aborted"] is None and len(site3.log) > 0
    assert len(db["od_valuation"].docs) == 6


def test_tdcc_skipped_when_recent_unless_forced():
    db = FakeDB()
    sync(db)
    site = Site()
    res, _ = sync(db, site=site, now=NOW + timedelta(hours=2))
    assert res["sources"]["tdcc_dist"]["skipped"] == "fresh" and site.count("/getOD.ashx") == 0
    st = next(d for d in db["od_state"].docs if d["_id"] == "tdcc")
    assert st["last_success_at"] == NOW + timedelta(hours=2)   # 略過不是失敗；仍算這輪成功
    site2 = Site()
    sync(db, site=site2, now=NOW + timedelta(hours=3), force=True)
    assert site2.count("/getOD.ashx") == 1
    # 離上一份滿 7 天 → 自動重抓
    site3 = Site()
    sync(db, site=site3, today=date(2026, 11, 12), now=NOW + timedelta(hours=4))
    assert site3.count("/getOD.ashx") == 0                          # 資料日 11/06、今天 11/12：才 6 天，不抓
    site4 = Site()
    sync(db, site=site4, today=date(2026, 11, 13), now=NOW + timedelta(days=1))
    assert site4.count("/getOD.ashx") == 1                          # 11/13：滿 7 天，開始每天問一次直到新的一份出現


def test_dataset_selection_and_unknown_names_ignored():
    db = FakeDB()
    res, site = sync(db, datasets=["revenue", "nope"])
    assert res["datasets"] == ["revenue"] and {x[1] for x in site.log} == {"/v1/opendata/t187ap05_L", "/openapi/v1/mopsfin_t187ap05_O"}
    assert db["od_margin"].docs == []


def test_empty_dataset_list_runs_nothing_but_leaves_a_record():
    db = FakeDB()
    res, site = sync(db, datasets=[])
    assert site.log == [] and res["rows"] == 0 and len(db["od_runs"].docs) == 1


def test_run_history_is_pruned():
    db = FakeDB()
    for i in range(od.RUNS_KEEP + 5):
        sync(db, datasets=[], now=NOW + timedelta(minutes=i))
    assert len(db["od_runs"].docs) == od.RUNS_KEEP


def test_only_one_run_at_a_time():
    db = FakeDB()

    async def while_another_run_holds_the_lock():
        async with od._run_lock:
            return await od.run_sync(db=db, now=NOW, today=TODAY)

    assert run(while_another_run_holds_the_lock()) == {"skipped": "already_running"}
    assert db.colls == {}   # 什麼都沒碰


# ───────────── 健康判斷 ─────────────
def _st(**kw):
    return {"last_success_at": NOW - timedelta(hours=2), "last_data_date": "2026-11-12", "last_error": None, **kw}


def test_health_statuses():
    states = {
        "margin": _st(),
        "valuation": _st(last_error="tpex_valuation：boom"),                              # partial
        "revenue": _st(last_success_at=NOW - timedelta(days=4)),                         # stale：4 天沒成功
        "tdcc": _st(last_data_date="2026-10-20"),                                         # stale：資料落後 23 天
        "disposal": {"last_success_at": None, "last_error": "twse_disposal：boom"},       # error
    }
    h = od.evaluate_health(states, TODAY, NOW)
    assert [h[k]["status"] for k in ("margin", "valuation", "revenue", "tdcc", "disposal", "attention")] == ["ok", "partial", "stale", "stale", "error", "never"]
    assert h["tdcc"]["data_age_days"] == 23
    s = od.summarize_health(h, None, NOW)
    assert s["ok"] is False and sorted(s["stale"]) == ["disposal", "revenue", "tdcc"] and s["partial"] == ["valuation"]


def test_health_long_weekend_is_not_stale_but_a_week_is():
    fri = _st(last_data_date="2026-11-13", last_success_at=NOW - timedelta(hours=30))
    assert od.evaluate_health({"margin": fri}, date(2026, 11, 16), NOW)["margin"]["status"] == "ok"      # 週五資料、週一檢查：3 天
    assert od.evaluate_health({"margin": fri}, date(2026, 11, 19), NOW)["margin"]["status"] == "stale"   # 6 天沒新資料才算過期


def test_health_all_ok_and_cooling_off_flag():
    ok_states = {ds: _st(last_data_date="2026-11-12") for ds in od.DATASETS}
    h = od.evaluate_health(ok_states, TODAY, NOW)
    assert od.summarize_health(h, None, NOW)["ok"] is True
    cooled = od.summarize_health(h, NOW + timedelta(hours=1), NOW)
    assert cooled["ok"] is False and cooled["cooling_off"] is True


def test_status_and_catch_up_after_a_run():
    db = FakeDB()
    assert run(od.needs_catch_up(db, now=NOW)) is True                                    # 從沒跑過 → 要補跑
    sync(db)
    assert run(od.needs_catch_up(db, now=NOW + timedelta(hours=2))) is False             # 剛成功
    assert run(od.needs_catch_up(db, now=NOW + timedelta(hours=31))) is True              # 超過 30 小時沒成功 → 補跑
    states, meta = run(od.load_states(db))
    assert set(states) == set(od.DATASETS) and meta == {}
    status = run(od.get_status(db))
    assert set(status["stored_counts"]) == set(od.DATASETS) and status["stored_counts"]["tdcc"] == 2
    assert len(status["recent_runs"]) == 1 and status["sources"]["margin"]["twse_margin"]["ok"] is True


# ───────────── 排程 ─────────────
def test_scheduler_open_data_runs_on_weekends_unlike_weekday_jobs(monkeypatch):
    from app import scheduler
    from datetime import timezone

    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 13, 22, 0, tzinfo=tz or timezone.utc)   # 週五 22:00（台灣）

    monkeypatch.setattr(scheduler, "datetime", FakeDT)
    assert scheduler._seconds_until_next_daily(21, 30) == pytest.approx(23.5 * 3600)           # 隔天（週六）21:30，照跑
    assert scheduler._seconds_until_next(21, 30) == pytest.approx((2 * 24 + 23.5) * 3600)      # 平日排程跳到週一
