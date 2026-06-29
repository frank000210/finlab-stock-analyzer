"""籌碼分析 — 大戶/散戶持股結構分析 (Shareholder Concentration Analysis).

資料來源：
- 集保戶股權分散表 (TDCC 開放資料, id=1-5) → 大戶/散戶持股結構
- FinMind 三大法人買賣超 → 主力動向 (透過 analyze_major_players)

集保戶股權分散表分級 (每張 = 1,000 股):
    Level 1  : 1-999 股        (零股)
    Level 2  : 1,000-5,000     (1-5 張)
    Level 3  : 5,001-10,000    (5-10 張)
    Level 4  : 10,001-15,000
    Level 5  : 15,001-20,000
    Level 6  : 20,001-30,000
    Level 7  : 30,001-40,000
    Level 8  : 40,001-50,000
    Level 9  : 50,001-100,000  (50-100 張)
    Level 10 : 100,001-200,000 (100-200 張)
    Level 11 : 200,001-400,000 (200-400 張)
    Level 12 : 400,001-600,000 (400-600 張)
    Level 13 : 600,001-800,000
    Level 14 : 800,001-1,000,000
    Level 15 : 1,000,001 以上   (千張大戶)
    Level 16 : 差異數調整
    Level 17 : 合計

分類定義:
    散戶   = Level 1-3   (持股 < 10 張)
    中實戶 = Level 9-11  (持股 50-400 張)
    大戶   = Level 12-15 (持股 > 400 張)
    千張大戶 = Level 15  (持股 > 1,000 張)
"""

import csv
import io
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

TDCC_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"

# In-process cache of the full TDCC table (same weekly file for every symbol).
# Avoids re-downloading ~2.3MB per request and survives transient DNS blips.
_TDCC_CACHE: dict = {"day": None, "rows": None}

LEVEL_LABELS = {
    "1": "1-999 股 (零股)",
    "2": "1-5 張",
    "3": "5-10 張",
    "4": "10-15 張",
    "5": "15-20 張",
    "6": "20-30 張",
    "7": "30-40 張",
    "8": "40-50 張",
    "9": "50-100 張",
    "10": "100-200 張",
    "11": "200-400 張",
    "12": "400-600 張",
    "13": "600-800 張",
    "14": "800-1000 張",
    "15": "1000 張以上 (千張大戶)",
}

RETAIL_LEVELS = {"1", "2", "3"}            # 散戶 < 10 張
MID_LEVELS = {"9", "10", "11"}            # 中實戶 50-400 張
WHALE_LEVELS = {"12", "13", "14", "15"}   # 大戶 > 400 張
MEGA_LEVEL = "15"                          # 千張大戶 > 1000 張


async def _fetch_tdcc() -> list[dict]:
    """Fetch the full TDCC distribution CSV (latest week, all stocks).

    Cached in-process per day and retried to absorb transient DNS/network
    failures seen on the host.
    """
    import asyncio

    today = datetime.utcnow().strftime("%Y%m%d")
    if _TDCC_CACHE["day"] == today and _TDCC_CACHE["rows"]:
        return _TDCC_CACHE["rows"]

    last_err = None
    for attempt in range(3):
        try:
            # TDCC's TLS chain trips strict OpenSSL on some hosts; this is public
            # open data with no auth, so verifying the cert adds no value here.
            async with httpx.AsyncClient(timeout=90, verify=False) as client:
                resp = await client.get(TDCC_URL)
                resp.raise_for_status()
                text = resp.content.decode("utf-8-sig", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return []
            header = rows[0]
            parsed = [dict(zip(header, r)) for r in rows[1:] if len(r) >= 6]
            _TDCC_CACHE["day"] = today
            _TDCC_CACHE["rows"] = parsed
            return parsed
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("TDCC fetch attempt %d failed: %s", attempt + 1, e)
            await asyncio.sleep(1.5 * (attempt + 1))

    # Fall back to a stale in-process copy if we have one, else raise.
    if _TDCC_CACHE["rows"]:
        logger.warning("TDCC fetch failed; serving stale in-process cache")
        return _TDCC_CACHE["rows"]
    raise last_err if last_err else RuntimeError("TDCC fetch failed")


def _parse_symbol_rows(all_rows: list[dict], symbol: str) -> dict | None:
    """Extract and structure the distribution for one symbol."""
    rows = [r for r in all_rows if r.get("證券代號", "").strip() == symbol]
    if not rows:
        return None

    data_date = rows[0].get("資料日期", "").strip()
    levels = {}
    total_people = 0
    total_shares = 0

    for r in rows:
        lv = r.get("持股分級", "").strip()
        try:
            people = int(r.get("人數", "0") or 0)
            shares = int(r.get("股數", "0") or 0)
            pct = float(r.get("占集保庫存數比例%", "0") or 0)
        except (ValueError, TypeError):
            continue
        if lv == "17":  # 合計
            total_people = people
            total_shares = shares
            continue
        if lv == "16":  # 差異數調整
            continue
        levels[lv] = {
            "level": lv,
            "label": LEVEL_LABELS.get(lv, lv),
            "people": people,
            "shares": shares,
            "percent": round(pct, 2),
        }

    def agg(level_set):
        people = sum(levels[l]["people"] for l in level_set if l in levels)
        shares = sum(levels[l]["shares"] for l in level_set if l in levels)
        percent = sum(levels[l]["percent"] for l in level_set if l in levels)
        return {"people": people, "shares": shares, "percent": round(percent, 2)}

    retail = agg(RETAIL_LEVELS)
    mid = agg(MID_LEVELS)
    whale = agg(WHALE_LEVELS)
    mega = agg({MEGA_LEVEL})

    return {
        "date": data_date,
        "total_holders": total_people,
        "total_shares": total_shares,
        "levels": [levels[str(i)] for i in range(1, 16) if str(i) in levels],
        "retail": retail,
        "mid": mid,
        "whale": whale,
        "mega": mega,
    }


async def _persist_snapshot(symbol: str, snapshot: dict) -> list[dict]:
    """Store the weekly snapshot in MongoDB and return historical trend."""
    history = []
    try:
        from ..db.mongodb import get_mongodb

        db = await get_mongodb()
        coll = db["chip_distribution"]
        doc = {
            "symbol": symbol,
            "date": snapshot["date"],
            "retail_pct": snapshot["retail"]["percent"],
            "mid_pct": snapshot["mid"]["percent"],
            "whale_pct": snapshot["whale"]["percent"],
            "mega_pct": snapshot["mega"]["percent"],
            "mega_people": snapshot["mega"]["people"],
            "whale_people": snapshot["whale"]["people"],
            "retail_people": snapshot["retail"]["people"],
            "total_holders": snapshot["total_holders"],
            "captured_at": datetime.utcnow(),
        }
        await coll.update_one(
            {"symbol": symbol, "date": snapshot["date"]},
            {"$set": doc},
            upsert=True,
        )
        cursor = coll.find({"symbol": symbol}).sort("date", 1)
        async for h in cursor:
            history.append({
                "date": h["date"],
                "retail_pct": h.get("retail_pct", 0),
                "mid_pct": h.get("mid_pct", 0),
                "whale_pct": h.get("whale_pct", 0),
                "mega_pct": h.get("mega_pct", 0),
                "mega_people": h.get("mega_people", 0),
                "whale_people": h.get("whale_people", 0),
                "retail_people": h.get("retail_people", 0),
                "total_holders": h.get("total_holders", 0),
            })
    except Exception as e:  # noqa: BLE001
        logger.warning("chip_distribution snapshot persist failed: %s", e)
    return history


def _build_movements(history: list[dict]) -> list[dict]:
    """Week-over-week 大戶進出記錄 from accumulated snapshots."""
    movements = []
    for i in range(1, len(history)):
        prev, cur = history[i - 1], history[i]
        movements.append({
            "date": cur["date"],
            "mega_pct": cur["mega_pct"],
            "mega_pct_change": round(cur["mega_pct"] - prev["mega_pct"], 2),
            "whale_pct": cur["whale_pct"],
            "whale_pct_change": round(cur["whale_pct"] - prev["whale_pct"], 2),
            "retail_pct": cur["retail_pct"],
            "retail_pct_change": round(cur["retail_pct"] - prev["retail_pct"], 2),
            "mega_people": cur["mega_people"],
            "mega_people_change": cur["mega_people"] - prev["mega_people"],
            "total_holders": cur["total_holders"],
            "holders_change": cur["total_holders"] - prev["total_holders"],
        })
    return movements[-12:]  # last 12 weeks


def _verdict(snapshot: dict, movements: list[dict]) -> dict:
    """Derive a chip-structure verdict and signals."""
    signals = []
    score = 0
    whale_pct = snapshot["whale"]["percent"]
    retail_pct = snapshot["retail"]["percent"]

    # Concentration level
    if whale_pct >= 70:
        signals.append({"label": f"大戶持股高度集中（{whale_pct:.1f}%）", "direction": "bullish"})
        score += 20
    elif whale_pct >= 50:
        signals.append({"label": f"大戶持股相對集中（{whale_pct:.1f}%）", "direction": "bullish"})
        score += 10
    elif whale_pct < 30:
        signals.append({"label": f"大戶持股偏低（{whale_pct:.1f}%），籌碼分散", "direction": "bearish"})
        score -= 10

    if retail_pct >= 30:
        signals.append({"label": f"散戶持股偏高（{retail_pct:.1f}%），籌碼凌亂", "direction": "bearish"})
        score -= 15
    elif retail_pct < 10:
        signals.append({"label": f"散戶持股極低（{retail_pct:.1f}%），籌碼穩定", "direction": "bullish"})
        score += 10

    # Trend (大戶進出)
    if movements:
        recent = movements[-1]
        if recent["mega_pct_change"] > 0.3:
            signals.append({"label": f"千張大戶本週增加 {recent['mega_pct_change']:.2f}%（吸籌）", "direction": "bullish"})
            score += 25
        elif recent["mega_pct_change"] < -0.3:
            signals.append({"label": f"千張大戶本週減少 {abs(recent['mega_pct_change']):.2f}%（出貨）", "direction": "bearish"})
            score -= 25
        if recent["holders_change"] < 0 and recent["mega_pct_change"] >= 0:
            signals.append({"label": "股東人數減少且大戶增加（籌碼集中中）", "direction": "bullish"})
            score += 15

    if score >= 30:
        verdict, desc = "籌碼集中", "大戶持股穩固，籌碼面偏多"
    elif score >= 10:
        verdict, desc = "偏多", "籌碼結構健康，略偏買方"
    elif score <= -30:
        verdict, desc = "籌碼分散", "散戶過多或大戶出脫，籌碼面偏空"
    elif score <= -10:
        verdict, desc = "偏空", "籌碼結構偏弱，需留意"
    else:
        verdict, desc = "中性", "籌碼結構中性，無明顯方向"

    return {
        "verdict": verdict,
        "verdict_description": desc,
        "score": score,
        "signals": signals,
    }


async def analyze_chip_distribution(symbol: str) -> dict:
    """Full 大戶/散戶 chip-structure analysis for one symbol."""
    try:
        all_rows = await _fetch_tdcc()
    except Exception as e:  # noqa: BLE001
        return {"error": f"無法取得集保戶股權分散表：{e}"}

    snapshot = _parse_symbol_rows(all_rows, symbol)
    if not snapshot:
        return {"error": f"集保資料中查無 {symbol} 的股權分散資料"}

    history = await _persist_snapshot(symbol, snapshot)
    movements = _build_movements(history)
    verdict = _verdict(snapshot, movements)

    return {
        "symbol": symbol,
        "data_date": snapshot["date"],
        "total_holders": snapshot["total_holders"],
        "distribution": snapshot["levels"],
        "structure": {
            "retail": snapshot["retail"],
            "mid": snapshot["mid"],
            "whale": snapshot["whale"],
            "mega": snapshot["mega"],
        },
        "movements": movements,
        "history_weeks": len(history),
        **verdict,
    }
