"""配息體檢串接：盤後日報段落、殖利率警報（建立驗證＋排程檢查）、訊息格式。

不碰 FinMind、不碰 MongoDB：get_setting／set_setting／報價／單檔快照／Telegram 全部換成假的。
"""

import asyncio

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analysis import etf_dividend_health as h


def _health(verdict="weak", inflation=1.31, labels=("殖利率膨脹", "近期趨勢")):
    levels = {"inflation": "warn", "stability": "good", "trend": "bad", "principal": "good"}
    names = {"inflation": "殖利率膨脹", "stability": "配息穩定度", "trend": "近期趨勢", "principal": "吃本金檢查"}
    checks = [{"key": k, "label": names[k], "level": (levels[k] if names[k] in labels else "good"), "text": "x"} for k in names]
    return {
        "enough": True, "reason": None, "verdict": verdict, "verdict_label": h.VERDICT_LABELS[verdict],
        "yield_now": 0.0857, "yield_norm": 0.0654, "inflation": inflation, "checks": checks,
        "scenarios": {"freq": 4, "freq_label": "季配", "conservative": 0.05, "neutral": 0.07, "last_annualized": 0.06},
    }


# ── 日報段落 ────────────────────────────────────────────────────────────────

def test_brief_lines_empty_when_nothing_judged():
    assert h.brief_lines([]) == []
    unknown = {"symbol": "00999", "name": "新", "health": {"enough": False, "reason": "不足", "checks": []}}
    assert h.brief_lines([unknown]) == []


def test_brief_lines_single_line_when_all_steady():
    steady = {"symbol": "0050", "name": "元大台灣50", "health": _health("steady", 1.0, labels=())}
    assert h.brief_lines([steady]) == ["✓ 配息體檢：觀察清單內 1 檔有配息的 ETF 都沒有警示"]


def test_brief_lines_lists_only_flagged_weak_first_with_reasons():
    watch = {"symbol": "00878", "name": "國泰永續高股息", "health": _health("watch", 1.12, labels=("殖利率膨脹",))}
    weak = {"symbol": "00919", "name": "群益台灣精選高息", "health": _health("weak", 1.31)}
    ok = {"symbol": "0050", "name": "元大台灣50", "health": _health("steady", 1.0, labels=())}
    lines = h.brief_lines([watch, ok, weak])
    assert lines[0].startswith("💰 配息體檢")
    assert len(lines) == 3  # 標題＋兩檔；穩定的不列
    assert "00919" in lines[1] and "偏弱" in lines[1] and "跌價撐高 1.31×" in lines[1] and "殖利率膨脹、近期趨勢" in lines[1]
    assert "00878" in lines[2] and "留意" in lines[2]
    assert not any("0050" in ln for ln in lines)


# ── 警報訊息 ────────────────────────────────────────────────────────────────

def test_yield_alert_message_carries_health_and_disclaimer():
    msg = h.yield_alert_message("00919", "群益台灣精選高息", 8.0, 0.0857, 20.5, _health("weak", 1.31))
    assert "殖利率警報：00919 群益台灣精選高息" in msg and "8.57%" in msg and "已達 8%" in msg and "收盤 20.5" in msg
    assert "配息體檢：偏弱" in msg and "跌價撐高 1.31×" in msg and "需留意：殖利率膨脹、近期趨勢" in msg
    assert "保守 5.0%／中性 7.0%／最近一次年化 6.0%" in msg
    assert "非投資建議" in msg


def test_yield_alert_message_without_or_insufficient_health():
    assert "配息體檢" not in h.yield_alert_message("0056", "", 7.0, 0.071, None, None).split("\n（")[0]
    short = {"enough": False, "reason": "除息紀錄只有 3 次", "checks": []}
    assert "資料不足（除息紀錄只有 3 次）" in h.yield_alert_message("00999", "", 7.0, 0.08, 10.0, short)


# ── 警報排程檢查 ────────────────────────────────────────────────────────────

class _Env:
    def __init__(self):
        self.alerts = []
        self.saved = None
        self.sent = []
        self.history = []
        self.snapshot = {"symbol": "00919", "yield_ttm": 0.0857, "last_close": 20.5, "last_date": "2026-11-03", "health": _health()}
        self.telegram_fails = False


@pytest.fixture()
def env(monkeypatch):
    e = _Env()
    import app.api.etf_compare as etf_api
    import app.api.risk as risk

    async def get_setting(key, default=None):
        return [dict(a) for a in e.alerts] if key == "price_alerts" else default

    async def set_setting(key, value):
        e.saved = value

    class FakeCrawler:
        async def get_price(self, sym, start, end, period):
            return pd.DataFrame({"date": pd.date_range("2026-10-01", periods=20), "close": [20.0 + i * 0.03 for i in range(20)],
                                 "volume": [1000.0] * 20})

    class FakeSettings:
        telegram_bot_token = "t"
        telegram_chat_id = "c"

    async def send_telegram(msg, token, chat):
        if e.telegram_fails:
            raise RuntimeError("network down")
        e.sent.append(msg)

    async def append_history(entry):
        e.history.append(entry)

    async def fake_snapshot(sym):
        return e.snapshot

    monkeypatch.setattr("app.db.cache.get_setting", get_setting)
    monkeypatch.setattr("app.db.cache.set_setting", set_setting)
    monkeypatch.setattr("app.crawler.stock_price.StockPriceCrawler", FakeCrawler)
    monkeypatch.setattr("app.config.settings.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.notify.telegram.send_telegram", send_telegram)
    monkeypatch.setattr(risk, "_append_alert_history", append_history)
    monkeypatch.setattr(etf_api, "yield_snapshot", fake_snapshot)
    return e, risk


def _yield_alert(target=7.0):
    return {"id": "y1", "symbol": "00919", "alert_type": "yield_target", "direction": "above", "target_price": None,
            "target_yield_pct": target, "last_yield_pct": None, "note": "", "active": True, "triggered": False,
            "triggered_at": None, "last_price": None, "last_checked_at": None}


def test_yield_alert_fires_once_with_health_message_and_history(env):
    e, risk = env
    e.alerts = [_yield_alert(7.0)]
    out = asyncio.run(risk.run_alert_check())
    assert out["triggered"] == 1
    assert len(e.sent) == 1 and "殖利率警報：00919" in e.sent[0] and "配息體檢：偏弱" in e.sent[0]
    saved = e.saved[0]
    assert saved["triggered"] is True and saved["last_yield_pct"] == 8.57
    assert e.history[0]["alert_type"] == "yield_target" and e.history[0]["yield_pct"] == 8.57 and e.history[0]["target_yield_pct"] == 7.0


def test_yield_alert_below_target_only_updates_last_yield(env):
    e, risk = env
    e.alerts = [_yield_alert(9.0)]
    out = asyncio.run(risk.run_alert_check())
    assert out["triggered"] == 0 and e.sent == [] and e.history == []
    assert e.saved[0]["triggered"] is False and e.saved[0]["last_yield_pct"] == 8.57


def test_yield_alert_with_no_snapshot_is_skipped_quietly(env):
    e, risk = env
    e.alerts = [_yield_alert(7.0)]
    e.snapshot = None
    out = asyncio.run(risk.run_alert_check())
    assert out["triggered"] == 0 and e.sent == []
    assert e.saved[0]["triggered"] is False and e.saved[0]["last_yield_pct"] is None


def test_yield_alert_stays_armed_when_telegram_fails(env):
    e, risk = env
    e.alerts = [_yield_alert(7.0)]
    e.telegram_fails = True
    out = asyncio.run(risk.run_alert_check())
    assert out["triggered"] == 0 and e.saved[0]["triggered"] is False  # 推播失敗留給下一輪，跟其他類型一致


# ── 建立警報的驗證 ──────────────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    import app.api.risk as risk
    from app.api.admin import require_admin

    pushed = []

    async def get_setting(key, default=None):
        return []

    async def push(key, item):
        pushed.append(item)

    monkeypatch.setattr("app.db.cache.get_setting", get_setting)
    monkeypatch.setattr("app.db.cache.push_to_setting_array", push)
    app = FastAPI()
    app.include_router(risk.router)
    app.dependency_overrides[require_admin] = lambda: None
    c = TestClient(app)
    c.pushed = pushed
    return c


@pytest.mark.parametrize("pct", [None, 0, -3, 50.01, 600])
def test_create_yield_alert_rejects_bad_target(client, pct):
    r = client.post("/api/v1/risk/alerts", json={"symbol": "00919", "alert_type": "yield_target", "target_yield_pct": pct})
    assert r.status_code == 400 and "目標殖利率" in r.json()["detail"]
    assert client.pushed == []


def test_create_yield_alert_ok_forces_above_and_no_price(client):
    r = client.post("/api/v1/risk/alerts", json={"symbol": "00919", "alert_type": "yield_target",
                                                 "direction": "below", "target_price": 123, "target_yield_pct": 7})
    assert r.status_code == 200
    a = r.json()["data"]
    assert a["alert_type"] == "yield_target" and a["direction"] == "above"
    assert a["target_price"] is None and a["target_yield_pct"] == 7 and a["last_yield_pct"] is None
    assert client.pushed == [a]


def test_existing_alert_types_unchanged(client):
    r = client.post("/api/v1/risk/alerts", json={"symbol": "2330", "alert_type": "price", "direction": "above", "target_price": 100})
    assert r.status_code == 200 and r.json()["data"]["target_yield_pct"] is None
    assert client.post("/api/v1/risk/alerts", json={"symbol": "2330", "alert_type": "price", "direction": "above"}).status_code == 400


# ── 日報整合 ────────────────────────────────────────────────────────────────

@pytest.fixture()
def brief_env(monkeypatch):
    import app.api.etf_compare as etf_api
    import app.api.risk as risk

    async def get_setting(key, default=None):
        return ["00919", "2330"] if key == "alert_symbols" else default

    async def regime():
        raise RuntimeError("skip")

    async def signals(symbols, lookback_days):
        return {"success": True, "data": {"as_of": "2026-11-03", "items": [
            {"ok": True, "symbol": "2330", "name": "台積電", "setup_total": 70, "trend": "多頭", "chg_pct": 1.0, "tags": []}]}}

    async def no_prose(*a, **k):
        return None

    monkeypatch.setattr("app.db.cache.get_setting", get_setting)
    monkeypatch.setattr(risk, "market_regime", regime)
    monkeypatch.setattr(risk, "watchlist_signals", signals)
    monkeypatch.setattr("app.analysis.daily_brief_llm.rewrite_brief_prose", no_prose)
    return etf_api, risk


def test_daily_brief_includes_dividend_health_section(brief_env, monkeypatch):
    etf_api, risk = brief_env

    async def items(symbols, limit=6):
        assert symbols == ["00919", "2330"]
        return [{"symbol": "00919", "name": "群益台灣精選高息", "health": _health("weak"), "yield_ttm": 0.0857}]

    monkeypatch.setattr(etf_api, "brief_dividend_health", items)
    text = asyncio.run(risk.build_daily_brief())["text"]
    assert "💰 配息體檢" in text and "00919" in text and "偏弱" in text
    assert text.index("配息體檢") < text.index("非投資建議")  # 段落在免責聲明之前


def test_daily_brief_survives_dividend_health_failure(brief_env, monkeypatch):
    etf_api, risk = brief_env

    async def boom(symbols, limit=6):
        raise RuntimeError("FinMind 402")

    monkeypatch.setattr(etf_api, "brief_dividend_health", boom)
    out = asyncio.run(risk.build_daily_brief())
    assert "盤後日報" in out["text"] and "配息體檢" not in out["text"]
