"""配息來源資料（analysis/etf_distribution.py＋API＋匯入腳本）：只收有出處、格式正確的資料。"""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analysis import etf_distribution as ed

ROOT = Path(__file__).resolve().parents[2]


def _entry(**o):
    e = {
        "symbol": "00919", "ex_date": "2026-06-17", "as_of": "2026-06-10",
        "per_unit": {"income": 0.40, "gain": 0.10, "equalization": 0.05, "principal": 0.0},
        "source": "○○投信 收益分配公告", "source_url": "https://example.com/notice/1",
    }
    e.update(o)
    return e


def test_valid_entry_passes():
    assert ed.validate_entry(_entry()) == []


@pytest.mark.parametrize("patch,needle", [
    ({"symbol": "bad code"}, "symbol"),
    ({"ex_date": "2026/06/17"}, "ex_date"),
    ({"as_of": ""}, "as_of"),
    ({"source": "  "}, "source"),
    ({"source_url": "http://insecure.example.com"}, "https://"),
    ({"source_url": ""}, "https://"),
    ({"per_unit": {"income": 1, "gain": 0, "equalization": 0}}, "per_unit"),
    ({"per_unit": {"income": -1, "gain": 0, "equalization": 0, "principal": 0}}, "≥ 0"),
    ({"per_unit": {"income": 0, "gain": 0, "equalization": 0, "principal": 0}}, "合計"),
    ({"per_unit": {"income": True, "gain": 0, "equalization": 0, "principal": 0}}, "≥ 0"),
])
def test_invalid_entries_are_rejected_with_a_reason(patch, needle):
    errs = ed.validate_entry(_entry(**patch))
    assert errs and any(needle in x for x in errs)


def test_entry_without_source_is_never_accepted():
    e = _entry()
    del e["source_url"]
    assert ed.validate_entry(e)


def test_merge_adds_replaces_and_rejects():
    a = _entry()
    merged, rep = ed.merge_entries([], [a])
    assert rep == {"added": 1, "replaced": 0, "rejected": []} and len(merged) == 1
    b = _entry(per_unit={"income": 0.2, "gain": 0.2, "equalization": 0.0, "principal": 0.1})
    merged, rep = ed.merge_entries(merged, [b, _entry(source="")])
    assert rep["replaced"] == 1 and rep["added"] == 0 and len(rep["rejected"]) == 1
    assert merged[0]["per_unit"]["principal"] == 0.1


def test_merge_sorts_and_uppercases_symbol():
    m, _ = ed.merge_entries([], [_entry(symbol="0056", ex_date="2026-07-01"), _entry(symbol="00878a", ex_date="2026-01-01"), _entry(symbol="0056", ex_date="2026-01-01")])
    assert [(x["symbol"], x["ex_date"]) for x in m] == [("0056", "2026-01-01"), ("0056", "2026-07-01"), ("00878A", "2026-01-01")]


def test_load_skips_invalid_missing_and_broken_files(tmp_path):
    assert ed.load_entries(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert ed.load_entries(bad) == {}
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"entries": [_entry(), _entry(source=""), _entry(ex_date="2026-03-18")]}, ensure_ascii=False), encoding="utf-8")
    got = ed.load_entries(ok)
    assert [e["ex_date"] for e in got["00919"]] == ["2026-03-18", "2026-06-17"]  # 無效的略過、依日期排序


def test_load_reflects_file_changes_without_restart(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"entries": [_entry()]}), encoding="utf-8")
    assert len(ed.load_entries(p)["00919"]) == 1
    import os
    p.write_text(json.dumps({"entries": [_entry(), _entry(ex_date="2026-09-16")]}), encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
    assert len(ed.load_entries(p)["00919"]) == 2


def test_shipped_data_file_is_valid_and_every_entry_has_a_source():
    doc = json.loads(ed.DATA_PATH.read_text(encoding="utf-8"))
    assert doc["schema_version"] == ed.SCHEMA_VERSION
    for e in doc["entries"]:
        assert ed.validate_entry(e) == [], e


@pytest.fixture()
def client(monkeypatch):
    from app.api.etf_compare import router

    async def _no_limit(key, cost=1, category="rate_limit"):
        return 1, 600

    monkeypatch.setattr("app.db.cache.consume_fixed_window", _no_limit)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_endpoint_returns_only_requested_symbols(client, monkeypatch):
    table = {"00919": [_entry()], "0056": [_entry(symbol="0056")]}
    monkeypatch.setattr("app.analysis.etf_distribution.load_entries", lambda path=None: table)
    r = client.get("/api/v1/etf-compare/distribution-sources", params={"symbols": "00919,00878"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert list(data["entries"]) == ["00919", "00878"]
    assert len(data["entries"]["00919"]) == 1 and data["entries"]["00878"] == []
    assert data["parts"] == ["income", "gain", "equalization", "principal"]


@pytest.mark.parametrize("q", ["", "0050;DROP"])
def test_endpoint_validates_symbols(client, q):
    assert client.get("/api/v1/etf-compare/distribution-sources", params={"symbols": q}).status_code == 400


def test_import_script_dry_run_reports_and_does_not_write(tmp_path):
    src = tmp_path / "rows.csv"
    with src.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "ex_date", "income", "gain", "equalization", "principal", "source", "source_url", "as_of"])
        w.writerow(["00919", "2026-06-17", "0.4", "0.1", "0.05", "0", "○○投信 公告", "https://example.com/n/1", "2026-06-10"])
        w.writerow(["00919", "2026-09-16", "0.4", "0.1", "0.05", "0", "", "https://example.com/n/2", "2026-09-10"])  # 缺來源
    before = ed.DATA_PATH.read_text(encoding="utf-8")
    p = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "scripts" / "etf_distribution_import.py"), str(src), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 1  # 有拒收的列 → 非 0，CI／人都看得到
    assert "新增 1 筆" in p.stdout and "拒收 1 筆" in p.stdout and "source" in p.stdout
    assert ed.DATA_PATH.read_text(encoding="utf-8") == before
