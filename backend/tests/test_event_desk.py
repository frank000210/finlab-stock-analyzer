"""事件研究台（app/analysis/event_desk.py）。

不連資料庫、不碰網路、不呼叫 LLM：Mongo 用假的集合、價格用假的抓取函式、LLM 用假的回應。
重點：日曆日期算得對（假日順延、連假後才反應）、內建資料全部合格且有出處、簡報格式擋得住壞資料、
價格反應的基準日不會選錯、AI 抽出的引文對不上原文會被標出來。
"""

import asyncio
import json
import sys
import types
from datetime import date

import pytest

from app.analysis import event_desk as ed

TODAY = date(2026, 11, 14)  # 星期六
NVDA_ID = "2026-11-12-nvda-ceo-transition"


def run(coro):
    return asyncio.run(coro)


# ───────────── 假的 Mongo ─────────────
class FakeResult:
    def __init__(self, deleted=0):
        self.deleted_count = deleted


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        self._it = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return dict(next(self._it))
        except StopIteration:
            raise StopAsyncIteration


class FakeColl:
    def __init__(self, fail=False):
        self.docs = {}
        self.fail = fail

    def find(self, flt=None):
        if self.fail:
            raise RuntimeError("mongo down")
        return FakeCursor(self.docs.values())

    async def find_one(self, flt):
        if self.fail:
            raise RuntimeError("mongo down")
        doc = self.docs.get(flt.get("_id"))
        return dict(doc) if doc else None

    async def update_one(self, flt, update, upsert=False):
        doc = self.docs.get(flt["_id"])
        if doc is None:
            if not upsert:
                return FakeResult()
            doc = {"_id": flt["_id"]}
            self.docs[flt["_id"]] = doc
        doc.update(update.get("$set", {}))
        return FakeResult()

    async def delete_one(self, flt):
        return FakeResult(1 if self.docs.pop(flt["_id"], None) is not None else 0)


class FakeDB:
    def __init__(self, fail=False):
        self.colls = {}
        self.fail = fail

    def __getitem__(self, name):
        return self.colls.setdefault(name, FakeColl(self.fail))


def minimal_brief(**over):
    b = {
        "id": "2026-12-01-test-event",
        "title": "測試事件",
        "kind": "shock",
        "event_date": "2026-12-01",
        "as_of": "2026-12-02",
        "summary": "測試用的最小簡報。",
        "facts": [{"text": "一則事實", "tier": 2, "source_name": "某媒體", "source_url": "https://example.com/a"}],
    }
    b.update(over)
    return b


# ───────────── 小工具與交易日 ─────────────
def test_date_and_url_checks():
    assert ed._check_iso("2026-11-14") == "2026-11-14"
    for bad in ("2026/11/14", "20261114", "2026-02-30", "", None):
        with pytest.raises((ValueError, TypeError)):
            ed._check_iso(bad)
    assert ed._check_url("") == ""
    assert ed._check_url(" https://example.com/x ") == "https://example.com/x"
    for bad in ("javascript:alert(1)", "ftp://x", "example.com", "https://a b"):
        with pytest.raises(ValueError):
            ed._check_url(bad)


def test_trading_days_respect_weekends_and_official_holidays():
    assert not ed.is_tw_trading_day(date(2026, 11, 14))  # 六
    assert ed.is_tw_trading_day(date(2026, 11, 16))
    assert not ed.is_tw_trading_day(date(2026, 12, 25))  # 行憲紀念日（五）
    # 2027 春節：2/1（一）最後交易日，2/2～2/10 休市，2/11 恢復
    assert ed.next_tw_trading_day(date(2027, 2, 1)) == date(2027, 2, 11)
    assert ed.next_tw_trading_day(date(2027, 2, 1), inclusive=True) == date(2027, 2, 1)
    assert ed.next_tw_trading_day(date(2026, 11, 13)) == date(2026, 11, 16)


def test_holiday_events_merge_blocks_and_skip_weekend_only_closures():
    evs = {e["date"]: e for e in ed.holiday_events(date(2026, 11, 14), date(2027, 12, 31))}
    lny = evs["2027-02-02"]
    assert lny["end_date"] == "2027-02-10"
    assert "農曆除夕及春節" in lny["title"]
    assert "少 7 個交易日" in lny["time_note"] and "2/11 恢復交易" in lny["time_note"]
    assert evs["2026-12-25"]["end_date"] is None and "12/28" in evs["2026-12-25"]["time_note"]
    # 2/28（日）＋3/1（一）補假 → 只算少 1 個交易日，日期記在 3/1
    assert "2027-02-28" not in evs and "少 1 個交易日" in evs["2027-03-01"]["time_note"]
    # 5/1（六）本身不產生事件，補假的 4/30（五）才有
    assert "2027-05-01" not in evs and "2027-04-30" in evs
    assert all(e["category"] == "tw_market" and e["source_url"] for e in evs.values())
    # 範圍外的不出現
    assert ed.holiday_events(date(2027, 3, 2), date(2027, 3, 31)) == []


def test_statutory_deadlines_roll_over_weekends_and_holidays():
    evs = {e["id"]: e for e in ed.statutory_events(date(2026, 11, 1), date(2027, 4, 15))}
    assert evs["twrev-2026-11"]["date"] == "2026-11-10"
    assert "10 月營收" in evs["twrev-2026-11"]["title"] and "順延" not in evs["twrev-2026-11"]["time_note"]
    # 11/14 是星期六 → 順延到 11/16
    assert evs["twfin-2026-11"]["date"] == "2026-11-16" and "順延" in evs["twfin-2026-11"]["time_note"]
    # 1/10 是星期日 → 1/11；2/10 在春節連假內 → 2/11
    assert evs["twrev-2027-01"]["date"] == "2027-01-11" and "12 月營收" in evs["twrev-2027-01"]["title"]
    assert evs["twrev-2027-02"]["date"] == "2027-02-11"
    assert evs["twfin-2027-03"]["date"] == "2027-03-31" and "年度財報" in evs["twfin-2027-03"]["title"]
    assert all(e["origin"] == "rule" for e in evs.values())


def test_statutory_one_day_range_returns_only_that_days_deadline():
    # 範圍只有一天時，只回剛好落在那天（順延後）的期限
    evs = ed.statutory_events(date(2027, 1, 11), date(2027, 1, 11))
    assert [e["id"] for e in evs] == ["twrev-2027-01"]


# ───────────── 日曆合併 ─────────────
def test_calendar_is_sorted_filtered_and_annotated():
    cal = ed.build_calendar(date(2026, 11, 10), date(2027, 3, 15), today=TODAY)
    dates = [e["date"] for e in cal]
    assert dates == sorted(dates)
    assert all("2026-11-10" <= (e.get("end_date") or e["date"]) and e["date"] <= "2027-03-15" for e in cal)
    ids = [e["id"] for e in cal]
    assert len(ids) == len(set(ids))
    by_id = {e["id"]: e for e in cal}
    nv = by_id["nvda-q3-fy2027"]
    assert nv["days_away"] == 3 and nv["weekday"] == "二" and nv["category_label"] == "財報／法說"
    # 美國時間的事件，台股下一個交易日才反應
    assert nv["tw_reaction_date"] == "2026-11-18"
    # 2/5 的就業報告落在春節連假 → 2/11 才反應
    assert by_id["us-jobs-2027-02-05"]["tw_reaction_date"] == "2027-02-11"
    assert by_id["twfin-2026-11"]["tw_reaction_date"] is None


def test_calendar_swaps_reversed_range_and_caps_span():
    a = ed.build_calendar(date(2026, 12, 31), date(2026, 12, 1), today=TODAY)
    b = ed.build_calendar(date(2026, 12, 1), date(2026, 12, 31), today=TODAY)
    assert [e["id"] for e in a] == [e["id"] for e in b] and a
    wide = ed.build_calendar(date(2026, 11, 14), date(2030, 1, 1), today=TODAY)
    assert max(e["date"] for e in wide) <= "2027-12-19"  # 400 天上限


def test_brief_key_date_merges_into_same_official_event_instead_of_duplicating():
    briefs = list(ed.load_builtin_briefs().values())
    cal = ed.build_calendar(date(2026, 11, 14), date(2026, 12, 31), briefs=briefs, today=TODAY)
    on_17 = [e for e in cal if e["date"] == "2026-11-17"]
    assert len(on_17) == 1 and on_17[0]["id"] == "nvda-q3-fy2027"
    assert on_17[0]["brief_id"] == NVDA_ID
    extra = [e for e in cal if e.get("origin") == "brief"]
    assert {e["date"] for e in extra} == {"2026-11-25", "2026-12-03", "2026-12-10"}
    assert all(e["brief_id"] == NVDA_ID and e["tentative"] for e in extra)


def test_custom_events_are_merged_and_get_stable_ids():
    doc = ed.custom_event_doc(ed.CustomEventIn(date="2026-11-21", title="某公司法說會", category="earnings"))
    same = ed.custom_event_doc(ed.CustomEventIn(date="2026-11-21", title="某公司法說會"))
    assert doc["id"] == same["id"] and doc["id"].startswith("c-")
    cal = ed.build_calendar(date(2026, 11, 20), date(2026, 11, 22), custom=[doc], today=TODAY)
    row = next(e for e in cal if e["id"] == doc["id"])
    assert row["origin"] == "custom"
    # 11/21 是星期六 → 台股 11/23 才能反應
    assert row["tw_reaction_date"] == "2026-11-23"


# ───────────── 內建資料 ─────────────
def test_every_builtin_calendar_event_is_valid_and_sourced():
    raw = json.loads(ed.CALENDAR_FILE.read_text(encoding="utf-8"))
    loaded = ed.load_builtin_events()
    assert len(loaded) == len(raw["events"]) >= 15  # 沒有任何一筆因格式錯誤被略過
    for e in loaded:
        assert e["source_url"].startswith("https://"), e["id"]
        assert e["verified_on"], e["id"]
        assert e["source_name"], e["id"]
    ids = [e["id"] for e in loaded]
    assert len(ids) == len(set(ids))
    meta = ed.calendar_meta()
    assert meta["verified_on"] and meta["holiday_source_url"].startswith("https://")


def test_every_builtin_brief_file_validates_and_is_complete():
    files = sorted(ed.BRIEFS_DIR.glob("*.json"))
    briefs = ed.load_builtin_briefs()
    assert len(briefs) == len(files) >= 1
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert path.stem == raw["id"], "檔名要等於 id"
        b = briefs[raw["id"]]
        assert b["builtin"] is True
        q = ed.brief_quality(b)
        assert q["passed"] == q["total"], [i["label"] for i in q["items"] if not i["ok"]]
        symbols, meta = ed.reaction_targets(b)
        assert len(symbols) <= ed.MAX_REACTION_SYMBOLS and set(symbols) == set(meta)


def test_nvda_brief_separates_confirmed_facts_from_reports():
    b = ed.load_builtin_briefs()[NVDA_ID]
    assert b["tw_base_date"] == "2026-11-12" and b["episode_start"] < b["tw_base_date"]
    unconfirmed = [f for f in b["facts"] if not f["confirmed"]]
    assert unconfirmed and all(f["tier"] >= 2 for f in unconfirmed)  # 官方來源不會被標成未證實
    assert {s["key"] for s in b["scenarios"]} == {"base", "bull", "bear"}
    assert all(s["triggers"] and s["invalidation"] for s in b["scenarios"])


# ───────────── 簡報格式 ─────────────
def test_minimal_brief_is_valid_and_defaults_are_filled():
    b, errors = ed.validate_brief(minimal_brief())
    assert errors == [] and b["status"] == "developing" and b["impact"] == [] and b["tw_base_date"] is None


@pytest.mark.parametrize("patch, needle", [
    ({"id": "Bad ID"}, "id"),
    ({"event_date": "2026/12/01"}, "event_date"),
    ({"facts": []}, "facts"),
    ({"facts": [{"text": "x", "tier": 4, "source_name": "s"}]}, "tier"),
    ({"facts": [{"text": "x", "tier": 2, "source_name": "s", "source_url": "javascript:alert(1)"}]}, "source_url"),
    ({"kind": "rumor"}, "kind"),
    ({"tw_base_date": "2026-12-01", "episode_start": "2026-12-05"}, "episode_start"),
    ({"as_of": "2026-11-30"}, "as_of"),
    ({"scenarios": [
        {"key": "base", "title": "a", "description": "d"},
        {"key": "base", "title": "b", "description": "d"},
    ]}, "不能重複"),
    ({"impact": [{"order": 1, "group": "g", "direction": "up", "mechanism": "m"}]}, "direction"),
    ({"impact": [{"order": 1, "group": "g", "direction": "hurt", "mechanism": "m",
                  "symbols": [{"symbol": "23 30"}]}]}, "symbol"),
])
def test_invalid_briefs_are_rejected_with_readable_errors(patch, needle):
    b, errors = ed.validate_brief(minimal_brief(**patch))
    assert b is None and errors
    assert any(needle in e for e in errors), errors


def test_scheduled_brief_may_be_written_before_the_event():
    b, errors = ed.validate_brief(minimal_brief(kind="scheduled", as_of="2026-11-20"))
    assert errors == [] and b["kind"] == "scheduled"


def test_quality_check_flags_missing_steps():
    b, _ = ed.validate_brief(minimal_brief())
    q = ed.brief_quality(b)
    failed = {i["key"] for i in q["items"] if not i["ok"]}
    assert failed == {"tier1", "independent", "expectation", "higher_order", "scenarios",
                      "invalidation", "key_dates", "unknowns"}
    assert q["passed"] == 1 and q["tier_counts"] == {"1": 0, "2": 1, "3": 0}

    # 第一手來源沒附網址不算數；兩個不同網域才算獨立
    b2, _ = ed.validate_brief(minimal_brief(facts=[
        {"text": "a", "tier": 1, "source_name": "公司公告"},
        {"text": "b", "tier": 2, "source_name": "m", "source_url": "https://www.example.com/1"},
        {"text": "c", "tier": 2, "source_name": "m", "source_url": "https://example.com/2", "confirmed": False},
    ]))
    q2 = ed.brief_quality(b2)
    by = {i["key"]: i["ok"] for i in q2["items"]}
    assert by["tier1"] is False and by["independent"] is False and by["sourced"] is False
    assert q2["unconfirmed_count"] == 1


def test_template_is_structurally_a_brief():
    t = ed.brief_template()
    assert set(t) >= {"id", "facts", "expectation", "impact", "scenarios", "key_dates", "open_questions"}
    assert {s["key"] for s in t["scenarios"]} == {"base", "bull", "bear"}


# ───────────── 儲存 ─────────────
def test_briefs_are_stored_listed_and_deleted():
    db = FakeDB()
    brief, _ = ed.validate_brief(minimal_brief())
    saved = run(ed.save_brief(brief, db))
    assert saved["builtin"] is False and saved["updated_at"]
    listed = run(ed.list_briefs(db))
    assert [b["id"] for b in listed][:2] == ["2026-12-01-test-event", NVDA_ID]  # 事件日期新的在前
    got = run(ed.get_brief("2026-12-01-test-event", db))
    assert got["title"] == "測試事件" and "_id" not in got
    assert run(ed.get_brief("nope", db)) is None
    assert run(ed.delete_brief("2026-12-01-test-event", db)) is True
    assert run(ed.delete_brief("2026-12-01-test-event", db)) is False


def test_builtin_briefs_cannot_be_overwritten_or_deleted():
    db = FakeDB()
    with pytest.raises(PermissionError):
        run(ed.save_brief({**minimal_brief(), "id": NVDA_ID}, db))
    with pytest.raises(PermissionError):
        run(ed.delete_brief(NVDA_ID, db))
    # 就算資料庫裡被塞了同 id 的文件，讀到的仍是內建版本
    db[ed.BRIEFS_COLL].docs[NVDA_ID] = {"_id": NVDA_ID, "id": NVDA_ID, "title": "被竄改", "event_date": "2026-11-12"}
    assert run(ed.get_brief(NVDA_ID, db))["title"] == "輝達執行長黃仁勳辭任"
    assert [b["title"] for b in run(ed.list_briefs(db)) if b["id"] == NVDA_ID] == ["輝達執行長黃仁勳辭任"]


def test_database_failure_falls_back_to_builtin_briefs():
    db = FakeDB(fail=True)
    assert [b["id"] for b in run(ed.list_briefs(db))] == [NVDA_ID]
    assert run(ed.get_brief("anything", db)) is None
    assert [b["id"] for b in run(ed.list_briefs(None))] == [NVDA_ID]


def test_brief_summary_has_quality_and_next_key_date():
    s = ed.brief_summary(ed.load_builtin_briefs()[NVDA_ID])
    assert s["quality_passed"] == s["quality_total"] == 9
    assert s["builtin"] is True and s["unconfirmed_count"] == 2


# ───────────── 價格反應 ─────────────
def series(start_close, closes_after, base_vol=1000, dates=None):
    dates = dates or ["2026-11-0%d" % d for d in (2, 3, 4, 5, 6)] + ["2026-11-09", "2026-11-10", "2026-11-11",
                                                                    "2026-11-12", "2026-11-13"]
    closes = [start_close] + list(closes_after)
    return [{"date": d, "close": c, "volume": base_vol} for d, c in zip(dates, closes)]


def test_reaction_uses_last_close_on_or_before_base_date():
    rows = series(100, [98, 96, 94, 90, 95, 97, 100, 96, 98])
    rows[-1]["volume"] = 3000
    r = ed.reaction_row(rows, "2026-11-12", "2026-11-02")
    assert r["base_date"] == "2026-11-12" and r["base_close"] == 96
    assert r["day1_date"] == "2026-11-13" and r["day1_pct"] == 2.08
    assert r["latest_pct"] == 2.08 and r["days_since"] == 1
    assert r["episode_from"] == "2026-11-02" and r["pre_pct"] == -4.0
    assert r["pre_low_pct"] == -10.0 and r["pre_low_date"] == "2026-11-06"
    assert r["vol_ratio_day1"] == 3.0
    assert r["ma20"] is None and r["above_ma20"] is None  # 資料不足 20 筆不硬算

    # 基準日是假日（沒有那天的資料）→ 用之前最後一個交易日
    r2 = ed.reaction_row(rows[:-2] + rows[-1:], "2026-11-12")
    assert r2["base_date"] == "2026-11-11" and r2["day1_date"] == "2026-11-13"
    assert r2["pre_pct"] is None


def test_reaction_handles_missing_and_not_yet_reacted_data():
    rows = series(100, [98, 96, 94, 90, 95, 97, 100, 96, 98])
    assert "error" in ed.reaction_row(rows, "2026-10-01")
    assert "error" in ed.reaction_row([], "2026-11-12")
    r = ed.reaction_row(rows[:-1], "2026-11-12")  # 事件後還沒有交易日
    assert r["day1_pct"] is None and r["latest_pct"] is None and r["path"] == [] and r["days_since"] == 0


def test_reaction_moving_averages_use_enough_history():
    dates = [date.fromordinal(date(2026, 8, 1).toordinal() + i).isoformat() for i in range(70)]
    rows = [{"date": d, "close": 100 + i, "volume": 10} for i, d in enumerate(dates)]
    r = ed.reaction_row(rows, dates[60])
    assert r["ma20"] == round(sum(range(150, 170)) / 20, 2) and r["above_ma20"] is True
    assert r["ma60"] is not None and r["above_ma60"] is True
    assert len(r["path"]) == 9  # 之後只有 9 個交易日


def test_compute_reaction_excess_only_when_dates_line_up():
    stock = series(100, [98, 96, 94, 90, 95, 97, 100, 96, 98])
    bench = series(1000, [990, 980, 970, 950, 960, 970, 990, 980, 990])
    stale = stock[:-1]  # 這檔少了最後一天
    out = ed.compute_reaction({"2330": stock, "9999": stale, "0000": []}, bench, "2026-11-12", "2026-11-02",
                              {"2330": {"name": "台積電"}})
    rows = {r["symbol"]: r for r in out["rows"]}
    assert out["bench"]["day1_pct"] == 1.02
    assert rows["2330"]["name"] == "台積電"
    assert rows["2330"]["day1_excess"] == round(2.08 - 1.02, 2)
    assert rows["2330"]["pre_excess"] == round(-4.0 - (-2.0), 2)
    assert rows["9999"]["day1_excess"] is None and rows["9999"]["latest_excess"] is None
    assert "error" in rows["0000"]


def test_fetch_reaction_collects_tw_symbols_and_reports_failures():
    brief = ed.load_builtin_briefs()[NVDA_ID]
    calls = []

    async def fake_fetch(symbol, start, end):
        calls.append((symbol, start, end))
        if symbol == "3324":
            raise RuntimeError("quota")
        return series(100, [98, 96, 94, 90, 95, 97, 100, 96, 98])

    out = run(ed.fetch_reaction(brief, fake_fetch, today=TODAY))
    symbols = [c[0] for c in calls]
    assert symbols.count("TAIEX") == 1 and len(symbols) == len(set(symbols)) == 19
    assert all(end == "2026-11-14" and start < "2026-07-01" for _, start, end in calls)
    assert out["errors"] == {"3324": "價格取得失敗"} and out["complete"] is False
    rows = {r["symbol"]: r for r in out["rows"]}
    assert rows["2330"]["name"] == "台積電" and rows["2330"]["order"] == 1
    assert "error" in rows["3324"] and rows["2317"]["day1_pct"] == 2.08

    async def ok_fetch(symbol, start, end):
        return series(100, [98, 96, 94, 90, 95, 97, 100, 96, 98])

    assert run(ed.fetch_reaction(brief, ok_fetch, today=TODAY))["complete"] is True


def test_fetch_reaction_needs_base_date_and_tw_symbols():
    b, _ = ed.validate_brief(minimal_brief())
    with pytest.raises(ValueError, match="tw_base_date"):
        run(ed.fetch_reaction(b))
    b2, _ = ed.validate_brief(minimal_brief(tw_base_date="2026-12-01", impact=[
        {"order": 1, "group": "美股", "direction": "hurt", "mechanism": "m", "symbols": [{"symbol": "NVDA"}]},
    ]))
    with pytest.raises(ValueError, match="台股代號"):
        run(ed.fetch_reaction(b2))


def test_reaction_targets_dedupe_normalise_and_cap():
    nodes = [{"order": 2, "group": "g", "direction": "mixed", "mechanism": "m",
              "symbols": [{"symbol": "2330.TW"}, {"symbol": "2330"}, {"symbol": "NVDA"}]}]
    nodes += [{"order": 2, "group": "g%d" % i, "direction": "mixed", "mechanism": "m",
               "symbols": [{"symbol": str(3000 + i * 10 + j)} for j in range(6)]} for i in range(5)]
    b, errors = ed.validate_brief(minimal_brief(impact=nodes))
    assert errors == []
    symbols, meta = ed.reaction_targets(b)
    assert symbols[0] == "2330" and "NVDA" not in symbols
    assert len(symbols) == ed.MAX_REACTION_SYMBOLS == len(meta)


# ───────────── 論點抽取 ─────────────
TRANSCRIPT = (
    "大家好，今天來聊輝達。我認為輝達下一季的營收還是會成長，因為雲端大廠的資本支出沒有下修。"
    "但是如果財報出來財測低於一千億美元，我就會改變看法。另外台積電的先進封裝產能到明年都是滿的，"
    "這個是公司在法說會上自己講的。短線上我覺得股價會在季線附近震盪，大家不要追高。"
    "最後提醒，融資的部分大家要注意，新興雲端業者的債務壓力很大，這一塊如果出事會拖累整個供應鏈。"
) * 2


def test_parse_llm_json_tolerates_fences_and_chatter():
    assert ed.parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ed.parse_llm_json('好的，以下是結果：{"a": {"b": 2}} 希望有幫助') == {"a": {"b": 2}}
    for bad in ("", "沒有 JSON", "[1,2]", "{壞掉"):
        with pytest.raises(ValueError):
            ed.parse_llm_json(bad)


def test_quote_matching_ignores_punctuation_but_catches_invented_quotes():
    norm = ed.normalize_for_match(TRANSCRIPT)
    assert ed.quote_match("我認為輝達下一季的營收還是會成長", norm) == "exact"
    assert ed.quote_match("我認為 輝達下一季的營收，還是會成長！", norm) == "exact"
    # 斷句不同、少數字不同 → 近似
    assert ed.quote_match("我認為輝達下一季的營收還是會成長因為雲端大廠資本支出沒有下修", norm) == "approx"
    # 原文沒有的話
    assert ed.quote_match("輝達明年股價會漲到三百美元以上", norm) == "none"
    assert ed.quote_match("短", norm) == "none" and ed.quote_match("", norm) == "none"


def test_postprocess_claims_normalises_and_verifies_quotes():
    raw = {
        "stance": "偏多",
        "claims": [
            {"quote": "我認為輝達下一季的營收還是會成長", "claim": "下一季營收會成長", "kind": "forecast",
             "assumptions": ["雲端大廠資本支出不下修"], "invalidation": "財測低於一千億美元", "horizon": "下一季",
             "checkable": True, "check_how": "看 11/17 財報的財測"},
            {"quote": "輝達明年股價會漲到三百美元以上", "claim": "股價會到 300 美元", "kind": "預測",
             "assumptions": "單一字串也接受", "checkable": False},
            {"quote": "x", "claim": "", "kind": "fact"},      # 沒有論點內容 → 丟掉
            "不是物件",                                         # 格式不對 → 丟掉
            {"claim": "沒有引文的論點", "kind": "亂寫"},
        ],
        "missing": "沒有說持股部位",
    }
    out = ed.postprocess_claims(raw, TRANSCRIPT)
    assert out["stance"] == "偏多" and out["missing"] == ["沒有說持股部位"]
    c = out["claims"]
    assert [x["quote_match"] for x in c] == ["exact", "none", "none"]
    assert [x["kind"] for x in c] == ["forecast", "forecast", "opinion"]
    assert c[1]["assumptions"] == ["單一字串也接受"] and c[2]["quote"] == ""
    assert out["stats"] == {"total": 3, "quote_verified": 1, "quote_unverified": 2,
                            "with_invalidation": 1, "forecasts": 2, "checkable": 1}
    assert ed.postprocess_claims({"stance": "強力買進", "claims": None}, TRANSCRIPT)["stance"] == "不明"
    many = {"claims": [{"claim": "c%d" % i} for i in range(30)]}
    assert len(ed.postprocess_claims(many, TRANSCRIPT)["claims"]) == ed.CLAIMS_MAX_ITEMS


def test_claims_input_bounds():
    with pytest.raises(ValueError, match="太短"):
        ed.check_claims_input("太短了")
    with pytest.raises(ValueError, match="分段"):
        ed.check_claims_input("字" * (ed.CLAIMS_MAX_CHARS + 1))
    assert ed.check_claims_input("  " + "字" * 300 + "  ") == "字" * 300


@pytest.fixture
def fake_cache(monkeypatch):
    """不讓測試去連真的 Mongo：把 app.db.cache 換成記憶體版。"""
    store = {}
    mod = types.ModuleType("app.db.cache")

    async def get_cache(key):
        return store.get(key)

    async def set_cache(key, data, category="analysis"):
        store[key] = data

    mod.get_cache, mod.set_cache = get_cache, set_cache
    monkeypatch.setitem(sys.modules, "app.db.cache", mod)
    return store


def test_extract_claims_calls_llm_once_and_caches(fake_cache):
    calls = []

    async def fake_llm(system, user, max_tokens=800, temperature=0.3):
        calls.append((system, user, max_tokens))
        return '```json\n' + json.dumps({
            "stance": "偏多",
            "claims": [{"quote": "台積電的先進封裝產能到明年都是滿的", "claim": "先進封裝產能滿載到明年",
                        "kind": "fact", "checkable": True, "check_how": "對照法說會逐字稿"}],
            "missing": [],
        }, ensure_ascii=False) + '\n```'

    out = run(ed.extract_claims(TRANSCRIPT, "某頻道", llm=fake_llm))
    assert out["cached"] is False and out["source"] == "某頻道" and out["chars"] == len(TRANSCRIPT)
    assert out["claims"][0]["quote_match"] == "exact" and out["stats"]["quote_verified"] == 1
    system, user, max_tokens = calls[0]
    assert "逐字照抄" in system and "不提供投資建議" in system and TRANSCRIPT in user and max_tokens >= 2000

    again = run(ed.extract_claims(TRANSCRIPT, "換個名字", llm=fake_llm))
    assert again["cached"] is True and again["source"] == "換個名字" and len(calls) == 1


def test_extract_claims_surfaces_bad_llm_output_and_does_not_cache_empty(fake_cache):
    async def garbage(system, user, **kw):
        return "抱歉，我沒辦法處理"

    with pytest.raises(ValueError):
        run(ed.extract_claims(TRANSCRIPT, llm=garbage))

    async def empty(system, user, **kw):
        return '{"stance": "不明", "claims": []}'

    out = run(ed.extract_claims(TRANSCRIPT, llm=empty))
    assert out["claims"] == [] and fake_cache == {}

    with pytest.raises(ValueError, match="太短"):
        run(ed.extract_claims("太短", llm=empty))
