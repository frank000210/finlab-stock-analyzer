"""Sector rotation (RRG) engine: TWSE sector indices -> Mongo -> RS-Ratio/RS-Momentum snapshots."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

from ..crawler.sector_index import BENCHMARK_ID, SectorIndexCrawler
from ..db.mongodb import get_mongodb
from .watch_graph import _best_lag_corr, _parse_date, _safe_float

QUADRANT_LEADING = "leading"      # 領先：RS-Ratio>100, RS-Momentum>100
QUADRANT_WEAKENING = "weakening"  # 轉弱：RS-Ratio>100, RS-Momentum<100
QUADRANT_LAGGING = "lagging"      # 落後：RS-Ratio<100, RS-Momentum<100
QUADRANT_IMPROVING = "improving"  # 轉強：RS-Ratio<100, RS-Momentum>100

_FREQ_PARAMS = {
    "daily": {"window": 50, "momentum": 10, "max_lag": 5},
    "weekly": {"window": 10, "momentum": 4, "max_lag": 3},
}


async def ensure_rotation_indexes(db=None) -> None:
    mongo = db if db is not None else await get_mongodb()
    await mongo.raw_sector_index.create_index([("sector_id", 1), ("date", 1)], unique=True)
    await mongo.raw_sector_index_days.create_index([("date", 1)], unique=True)


async def ingest_sector_index(
    start_date: str | date,
    end_date: str | date,
    max_fetch_days: int = 260,
) -> dict[str, Any]:
    """Backfill TWSE sector index closes into Mongo, skipping cached days.

    Holidays are cached as empty markers so they are never re-fetched.

    最近 2 天內的空結果不視為「已知」（不永久快取）——TWSE 的 MI_INDEX 通常收盤後
    要等一段時間才會發布當日資料，若排程在資料還沒發布前就跑（例如台股 13:30
    收盤、排程 15:00 就執行），會抓到空結果。若把這種「還沒發布」跟「真的是假日」
    同樣永久快取，類股輪動會卡在前一個交易日，就算之後 TWSE 資料已經發布也不會
    重試。給最近 2 天一個重試窗口（涵蓋今天 + 下一次排程執行時），過了這個窗口
    才視為確定的假日並永久快取，避免無限重試已經確認沒有資料的舊日期。
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    retry_window = {(date.today() - timedelta(days=offset)).isoformat() for offset in (0, 1)}
    mongo = await get_mongodb()
    await ensure_rotation_indexes(mongo)

    known_cursor = mongo.raw_sector_index_days.find(
        {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}},
        {"_id": 0, "date": 1, "row_count": 1},
    )
    known_dates = {
        doc["date"]
        for doc in await known_cursor.to_list(length=None)
        if not (doc["date"] in retry_window and not doc.get("row_count"))
    }

    missing: list[date] = []
    cursor_day = start
    while cursor_day <= end:
        if cursor_day.weekday() < 5 and cursor_day.isoformat() not in known_dates:
            missing.append(cursor_day)
        cursor_day += timedelta(days=1)
    missing = missing[-max_fetch_days:]

    crawler = SectorIndexCrawler()
    fetched = await crawler.get_days(missing)

    now = datetime.utcnow()
    inserted_rows = 0
    trading_days = 0
    for iso_day, rows in fetched.items():
        await mongo.raw_sector_index_days.update_one(
            {"date": iso_day},
            {"$set": {"date": iso_day, "row_count": len(rows), "updated_at": now}},
            upsert=True,
        )
        if not rows:
            continue
        trading_days += 1
        for row in rows:
            await mongo.raw_sector_index.update_one(
                {"sector_id": row["sector_id"], "date": iso_day},
                {
                    "$set": {
                        "sector_id": row["sector_id"],
                        "name": row["name"],
                        "date": iso_day,
                        "close": float(row["close"]),
                        "is_benchmark": bool(row.get("is_benchmark")),
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
            inserted_rows += 1

    return {
        "requested_days": len(missing),
        "trading_days": trading_days,
        "rows": inserted_rows,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


async def _load_twse_series(start: date, end: date) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """Return ({sector_id: {date: close}}, {sector_id: display name}); includes TAIEX."""
    mongo = await get_mongodb()
    cursor = mongo.raw_sector_index.find(
        {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}},
        {"_id": 0, "sector_id": 1, "name": 1, "date": 1, "close": 1},
    )
    docs = await cursor.to_list(length=None)
    series: dict[str, dict[str, float]] = {}
    names: dict[str, str] = {}
    for doc in docs:
        sid = doc["sector_id"]
        series.setdefault(sid, {})[doc["date"]] = _safe_float(doc.get("close"))
        names[sid] = str(doc.get("name") or sid)
    return series, names


async def _load_watchlist_series(
    symbols: list[str], start: date, end: date
) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """Aggregate watchlist stocks into equal-weight industry indices (base=100)."""
    mongo = await get_mongodb()
    normalized = [str(s or "").strip().upper() for s in symbols if str(s or "").strip()]
    if not normalized:
        return {}, {}

    industry_docs = await mongo.raw_industry.find(
        {"symbol": {"$in": normalized}}, {"_id": 0}
    ).to_list(length=None)
    industry_of = {doc["symbol"]: str(doc.get("industry") or "未知產業") for doc in industry_docs}

    price_docs = await mongo.raw_prices.find(
        {"symbol": {"$in": normalized}, "date": {"$gte": start.isoformat(), "$lte": end.isoformat()}},
        {"_id": 0, "symbol": 1, "date": 1, "close": 1},
    ).to_list(length=None)

    closes: dict[str, dict[str, float]] = {}
    for doc in price_docs:
        sym = str(doc.get("symbol", "")).upper()
        value = _safe_float(doc.get("close"))
        if value > 0:
            closes.setdefault(sym, {})[doc["date"]] = value

    # Normalize each stock to 100 at its first observation, then average per industry.
    normalized_series: dict[str, dict[str, float]] = {}
    for sym, by_date in closes.items():
        ordered = sorted(by_date.items())
        if not ordered:
            continue
        base = ordered[0][1]
        if base <= 0:
            continue
        normalized_series[sym] = {d: 100.0 * v / base for d, v in ordered}

    groups: dict[str, list[str]] = {}
    for sym in normalized_series:
        groups.setdefault(industry_of.get(sym, "未知產業"), []).append(sym)

    series: dict[str, dict[str, float]] = {}
    names: dict[str, str] = {}
    all_dates: set[str] = set()
    for by_date in normalized_series.values():
        all_dates.update(by_date)

    for industry, members in groups.items():
        sector_curve: dict[str, float] = {}
        for iso_day in sorted(all_dates):
            values = [normalized_series[m][iso_day] for m in members if iso_day in normalized_series[m]]
            if values:
                sector_curve[iso_day] = float(np.mean(values))
        if len(sector_curve) >= 5:
            series[industry] = sector_curve
            names[industry] = f"{industry}（{len(members)}檔）"

    # Benchmark = equal weight of the whole watchlist.
    bench_curve: dict[str, float] = {}
    for iso_day in sorted(all_dates):
        values = [by_date[iso_day] for by_date in normalized_series.values() if iso_day in by_date]
        if values:
            bench_curve[iso_day] = float(np.mean(values))
    if bench_curve:
        series[BENCHMARK_ID] = bench_curve
        names[BENCHMARK_ID] = "觀察池等權指數"

    return series, names


def _resample_weekly(series: dict[str, float]) -> dict[str, float]:
    """Keep the last close of each ISO week, keyed by that day's date."""
    weekly: dict[tuple[int, int], tuple[str, float]] = {}
    for iso_day in sorted(series):
        day = datetime.strptime(iso_day, "%Y-%m-%d").date()
        key = day.isocalendar()[:2]
        weekly[key] = (iso_day, series[iso_day])
    return {iso_day: value for iso_day, value in weekly.values()}


def _trailing_zscore(values: np.ndarray, window: int) -> np.ndarray:
    """z-score of each point against its trailing window (inclusive)."""
    result = np.full(len(values), np.nan)
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo : i + 1]
        chunk = chunk[np.isfinite(chunk)]
        if len(chunk) < max(3, window // 2):
            continue
        std = float(np.std(chunk))
        if std <= 1e-12:
            result[i] = 0.0
        else:
            result[i] = (values[i] - float(np.mean(chunk))) / std
    return result


def _quadrant(x: float, y: float) -> str:
    if x >= 100 and y >= 100:
        return QUADRANT_LEADING
    if x >= 100:
        return QUADRANT_WEAKENING
    if y >= 100:
        return QUADRANT_IMPROVING
    return QUADRANT_LAGGING


def _phase_angle(x: float, y: float) -> float:
    """Angle in degrees (0-360) around (100,100); RRG rotates clockwise."""
    angle = float(np.degrees(np.arctan2(y - 100.0, x - 100.0)))
    return angle % 360.0


def compute_rrg_series(
    series: dict[str, dict[str, float]],
    freq: str = "daily",
) -> dict[str, Any]:
    """Compute JdK-style RS-Ratio / RS-Momentum for every sector vs the benchmark.

    Returns {dates: [...], sectors: {sector_id: {rs_ratio: [...], rs_momentum: [...]}}}.
    """
    params = _FREQ_PARAMS.get(freq, _FREQ_PARAMS["daily"])
    window = params["window"]
    momentum = params["momentum"]

    bench = series.get(BENCHMARK_ID) or {}
    if freq == "weekly":
        bench = _resample_weekly(bench)
    if len(bench) < window + momentum:
        return {"dates": [], "sectors": {}}

    bench_dates = sorted(bench)
    result_sectors: dict[str, dict[str, list[float | None]]] = {}

    for sector_id, raw_curve in series.items():
        if sector_id == BENCHMARK_ID:
            continue
        curve = _resample_weekly(raw_curve) if freq == "weekly" else raw_curve
        aligned_dates = [d for d in bench_dates if d in curve]
        if len(aligned_dates) < window + momentum:
            continue
        rs = np.array([100.0 * curve[d] / bench[d] for d in aligned_dates])
        rs_ratio = 100.0 + _trailing_zscore(rs, window)

        roc = np.full(len(rs_ratio), np.nan)
        for i in range(momentum, len(rs_ratio)):
            prev = rs_ratio[i - momentum]
            if np.isfinite(prev) and prev != 0 and np.isfinite(rs_ratio[i]):
                roc[i] = 100.0 * (rs_ratio[i] - prev) / abs(prev)
        rs_momentum = 100.0 + _trailing_zscore(roc, window)

        by_date_ratio = dict(zip(aligned_dates, rs_ratio))
        by_date_mom = dict(zip(aligned_dates, rs_momentum))
        result_sectors[sector_id] = {
            "rs_ratio": [
                round(float(by_date_ratio[d]), 3) if d in by_date_ratio and np.isfinite(by_date_ratio[d]) else None
                for d in bench_dates
            ],
            "rs_momentum": [
                round(float(by_date_mom[d]), 3) if d in by_date_mom and np.isfinite(by_date_mom[d]) else None
                for d in bench_dates
            ],
        }

    return {"dates": bench_dates, "sectors": result_sectors}


def _build_points(
    rrg: dict[str, Any],
    names: dict[str, str],
    index: int,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for sector_id, data in rrg["sectors"].items():
        x = data["rs_ratio"][index]
        y = data["rs_momentum"][index]
        if x is None or y is None:
            continue
        points.append(
            {
                "id": sector_id,
                "name": names.get(sector_id, sector_id),
                "rs_ratio": x,
                "rs_momentum": y,
                "quadrant": _quadrant(x, y),
                "angle": round(_phase_angle(x, y), 2),
            }
        )
    return points


def _build_lead_edges(
    rrg: dict[str, Any],
    freq: str,
    edge_threshold: float,
) -> list[dict[str, Any]]:
    """Directed lead-lag edges between sectors from RS-Ratio changes."""
    params = _FREQ_PARAMS.get(freq, _FREQ_PARAMS["daily"])
    max_lag = params["max_lag"]
    returns: dict[str, list[float]] = {}
    for sector_id, data in rrg["sectors"].items():
        values = [v for v in data["rs_ratio"]]
        diffs: list[float] = []
        prev: float | None = None
        for v in values:
            if v is not None and prev is not None:
                diffs.append(v - prev)
            elif v is not None:
                diffs.append(0.0)
            prev = v if v is not None else prev
        returns[sector_id] = diffs

    sector_ids = list(returns)
    edges: list[dict[str, Any]] = []
    for i, src in enumerate(sector_ids):
        for dst in sector_ids[i + 1 :]:
            lag, corr = _best_lag_corr(returns[src], returns[dst], max_lag=max_lag)
            if abs(corr) < edge_threshold or lag == 0:
                continue
            edges.append(
                {
                    "src": src,
                    "dst": dst,
                    "lag": lag,
                    "weight": round(float(corr), 4),
                    "abs_weight": round(abs(float(corr)), 4),
                    "directed": True,
                }
            )
            lag_rev, corr_rev = _best_lag_corr(returns[dst], returns[src], max_lag=max_lag)
            if abs(corr_rev) >= edge_threshold and lag_rev > 0:
                edges.append(
                    {
                        "src": dst,
                        "dst": src,
                        "lag": lag_rev,
                        "weight": round(float(corr_rev), 4),
                        "abs_weight": round(abs(float(corr_rev)), 4),
                        "directed": True,
                    }
                )
    edges.sort(key=lambda e: -e["abs_weight"])
    return edges[:60]


def _build_ranking(points: list[dict[str, Any]], prev_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rotation order: 領先 -> 轉弱 -> 落後 -> 轉強 (clockwise), with angular velocity."""
    prev_angle = {p["id"]: p["angle"] for p in prev_points}
    quadrant_order = {
        QUADRANT_LEADING: 0,
        QUADRANT_WEAKENING: 1,
        QUADRANT_LAGGING: 2,
        QUADRANT_IMPROVING: 3,
    }
    ranked = []
    for p in points:
        velocity = 0.0
        if p["id"] in prev_angle:
            delta = prev_angle[p["id"]] - p["angle"]  # clockwise = angle decreasing
            if delta > 180:
                delta -= 360
            elif delta < -180:
                delta += 360
            velocity = round(delta, 2)
        strength = float(np.hypot(p["rs_ratio"] - 100.0, p["rs_momentum"] - 100.0))
        ranked.append({**p, "angular_velocity": velocity, "strength": round(strength, 3)})
    ranked.sort(key=lambda p: (quadrant_order.get(p["quadrant"], 9), -p["strength"]))
    return ranked


async def get_rotation_snapshot(
    universe: str = "twse",
    freq: str = "daily",
    target_date: str | date | None = None,
    symbols: list[str] | None = None,
    lookback_days: int = 400,
    trail_length: int = 10,
    edge_threshold: float = 0.25,
) -> dict[str, Any]:
    end = _parse_date(target_date)
    start = end - timedelta(days=lookback_days if freq == "daily" else max(lookback_days, 800))

    if universe == "watchlist":
        series, names = await _load_watchlist_series(symbols or [], start, end)
    else:
        series, names = await _load_twse_series(start, end)

    rrg = compute_rrg_series(series, freq=freq)
    dates = rrg["dates"]
    if not dates:
        return {"date": end.isoformat(), "freq": freq, "universe": universe, "points": [], "trails": {}, "lead_edges": [], "ranking": []}

    # Snap to the latest available date <= target.
    idx = len(dates) - 1
    for i in range(len(dates) - 1, -1, -1):
        if dates[i] <= end.isoformat():
            idx = i
            break

    points = _build_points(rrg, names, idx)
    prev_points = _build_points(rrg, names, idx - 1) if idx > 0 else []
    trails: dict[str, list[dict[str, Any]]] = {}
    for sector_id, data in rrg["sectors"].items():
        trail = []
        for j in range(max(0, idx - trail_length + 1), idx + 1):
            x = data["rs_ratio"][j]
            y = data["rs_momentum"][j]
            if x is not None and y is not None:
                trail.append({"date": dates[j], "x": x, "y": y})
        if trail:
            trails[sector_id] = trail

    return {
        "date": dates[idx],
        "freq": freq,
        "universe": universe,
        "params": _FREQ_PARAMS.get(freq, _FREQ_PARAMS["daily"]),
        "points": points,
        "trails": trails,
        "lead_edges": _build_lead_edges(rrg, freq, edge_threshold),
        "ranking": _build_ranking(points, prev_points),
    }


async def get_rotation_timeline(
    universe: str = "twse",
    freq: str = "daily",
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    symbols: list[str] | None = None,
    lookback_days: int = 400,
) -> dict[str, Any]:
    end = _parse_date(end_date)
    start = _parse_date(start_date, end - timedelta(days=60))
    load_start = start - timedelta(days=lookback_days if freq == "daily" else max(lookback_days, 800))

    if universe == "watchlist":
        series, names = await _load_watchlist_series(symbols or [], load_start, end)
    else:
        series, names = await _load_twse_series(load_start, end)

    rrg = compute_rrg_series(series, freq=freq)
    items = []
    for i, iso_day in enumerate(rrg["dates"]):
        if iso_day < start.isoformat() or iso_day > end.isoformat():
            continue
        points = _build_points(rrg, names, i)
        if points:
            items.append({"date": iso_day, "points": points})

    return {"freq": freq, "universe": universe, "items": items}


async def get_daily_heatmap(
    universe: str = "twse",
    target_date: str | date | None = None,
    symbols: list[str] | None = None,
    lookback_days: int = 10,
) -> dict[str, Any]:
    """Latest-day % change per sector/industry group, for a market-pulse treemap.

    Unlike the RRG snapshot (RS-Ratio/RS-Momentum vs benchmark, smoothed over a
    trailing window), this is a plain same-day close-vs-previous-close snapshot:
    D3 gallery 參考: Treemap -- size = |pct_change| (今天動最大的類股方塊最大),
    color = sign (漲綠跌紅)。
    """
    end = _parse_date(target_date)
    start = end - timedelta(days=lookback_days)

    if universe == "watchlist":
        series, names = await _load_watchlist_series(symbols or [], start, end)
    else:
        series, names = await _load_twse_series(start, end)

    items: list[dict[str, Any]] = []
    for sector_id, curve in series.items():
        if sector_id == BENCHMARK_ID:
            continue
        dates = sorted(d for d in curve if d <= end.isoformat())
        if len(dates) < 2:
            continue
        last_day, prev_day = dates[-1], dates[-2]
        last_close = curve[last_day]
        prev_close = curve[prev_day]
        if prev_close <= 0:
            continue
        pct = (last_close - prev_close) / prev_close * 100.0
        items.append(
            {
                "id": sector_id,
                "name": names.get(sector_id, sector_id),
                "date": last_day,
                "close": round(float(last_close), 3),
                "pct_change": round(float(pct), 2),
            }
        )

    items.sort(key=lambda it: -abs(it["pct_change"]))
    latest_date = items[0]["date"] if items else end.isoformat()
    return {"date": latest_date, "universe": universe, "items": items}
