"""Watchlist graph modeling: crawler -> Mongo raw -> feature -> graph snapshots."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

from ..crawler import FinMindClient, InstitutionalCrawler, StockPriceCrawler
from ..db.mongodb import get_mongodb

DEFAULT_ALPHA = 0.50
DEFAULT_BETA = 0.30
DEFAULT_GAMMA = 0.20


def _normalize_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in symbols or []:
        symbol = str(raw or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _watchlist_hash(symbols: list[str]) -> str:
    joined = ",".join(sorted(_normalize_symbols(symbols)))
    return hashlib.md5(joined.encode("utf-8")).hexdigest()  # noqa: S324


def _parse_date(value: str | date | None, fallback: date | None = None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    return fallback or date.today()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
        if np.isfinite(num):
            return num
    except Exception:
        pass
    return default


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) >= 10:
        return text[:10]
    return text


def _edge_key(src: str, dst: str) -> str:
    return f"{src}->{dst}"


def _corr(values_a: list[float], values_b: list[float]) -> float:
    if len(values_a) < 20 or len(values_b) < 20 or len(values_a) != len(values_b):
        return 0.0
    arr_a = np.array(values_a, dtype=float)
    arr_b = np.array(values_b, dtype=float)
    if np.std(arr_a) == 0 or np.std(arr_b) == 0:
        return 0.0
    corr = float(np.corrcoef(arr_a, arr_b)[0, 1])
    return corr if np.isfinite(corr) else 0.0


def _best_lag_corr(values_a: list[float], values_b: list[float], max_lag: int = 5) -> tuple[int, float]:
    best_lag = 0
    best_corr = 0.0
    for lag in range(1, max_lag + 1):
        if len(values_a) <= lag or len(values_b) <= lag:
            continue
        corr = _corr(values_a[:-lag], values_b[lag:])
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag
    return best_lag, best_corr


def _pagerank(nodes: list[str], edges: list[dict[str, Any]], damping: float = 0.85, steps: int = 24) -> dict[str, float]:
    if not nodes:
        return {}
    n = len(nodes)
    ranks = {node: 1.0 / n for node in nodes}
    outgoing: dict[str, list[tuple[str, float]]] = {node: [] for node in nodes}
    for edge in edges:
        src = edge.get("src")
        dst = edge.get("dst")
        weight = abs(_safe_float(edge.get("weight")))
        if src in outgoing and dst in outgoing and src != dst and weight > 0:
            outgoing[src].append((dst, weight))

    for _ in range(steps):
        updated = {node: (1.0 - damping) / n for node in nodes}
        for src, links in outgoing.items():
            if not links:
                continue
            total_weight = sum(weight for _, weight in links) or 1.0
            for dst, weight in links:
                updated[dst] += damping * ranks[src] * (weight / total_weight)
        ranks = updated
    return {k: round(v, 6) for k, v in ranks.items()}


def _derive_node_metrics(symbols: list[str], fusion_edges: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    metrics = {
        symbol: {
            "in_weight": 0.0,
            "out_weight": 0.0,
            "in_degree": 0.0,
            "out_degree": 0.0,
            "risk_transmission": 0.0,
        }
        for symbol in symbols
    }
    for edge in fusion_edges:
        src = edge.get("src")
        dst = edge.get("dst")
        weight = _safe_float(edge.get("weight"))
        if src not in metrics or dst not in metrics:
            continue
        metrics[src]["out_weight"] += abs(weight)
        metrics[src]["out_degree"] += 1
        metrics[dst]["in_weight"] += abs(weight)
        metrics[dst]["in_degree"] += 1
        if weight < 0:
            metrics[dst]["risk_transmission"] += abs(weight)

    max_total = max((v["in_weight"] + v["out_weight"] for v in metrics.values()), default=1.0) or 1.0
    for value in metrics.values():
        total = value["in_weight"] + value["out_weight"]
        value["weighted_degree"] = total
        value["centrality"] = total / max_total
    return metrics


async def ensure_graph_indexes(db=None) -> None:
    mongo = db if db is not None else await get_mongodb()
    await mongo.raw_prices.create_index([("symbol", 1), ("date", 1)], unique=True)
    await mongo.raw_institutional.create_index([("symbol", 1), ("date", 1)], unique=True)
    await mongo.raw_industry.create_index([("symbol", 1)], unique=True)
    await mongo.feature_nodes_daily.create_index([("watchlist_hash", 1), ("date", -1)])
    await mongo.feature_edges_daily.create_index([("watchlist_hash", 1), ("date", -1)])
    await mongo.graph_snapshots.create_index([("watchlist_hash", 1), ("date", -1)], unique=True)
    await mongo.graph_alerts.create_index([("watchlist_hash", 1), ("created_at", -1)])


async def ingest_watchlist_raw(
    symbols: list[str],
    start_date: str | date,
    end_date: str | date,
) -> dict[str, Any]:
    symbols = _normalize_symbols(symbols)
    if not symbols:
        return {"symbols": 0, "prices": 0, "institutional": 0, "industry": 0}

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    mongo = await get_mongodb()
    await ensure_graph_indexes(mongo)

    stock_crawler = StockPriceCrawler()
    inst_crawler = InstitutionalCrawler()
    finmind = FinMindClient()

    info_df = await finmind.get_stock_info()
    info_map: dict[str, dict[str, Any]] = {}
    if not info_df.empty:
        for _, row in info_df.iterrows():
            sid = str(row.get("stock_id", "")).strip().upper()
            if sid:
                info_map[sid] = {
                    "name_zh": str(row.get("stock_name", "") or "").strip(),
                    "industry": str(row.get("Industry_category", "") or "").strip(),
                }

    inserted_prices = 0
    inserted_inst = 0
    inserted_industry = 0
    now = datetime.utcnow()

    for symbol in symbols:
        try:
            df = await stock_crawler.get_price(symbol, start.isoformat(), end.isoformat(), "1d")
            if not df.empty:
                for _, row in df.iterrows():
                    iso_date = _to_iso(row.get("date"))
                    if not iso_date:
                        continue
                    doc = {
                        "symbol": symbol,
                        "date": iso_date,
                        "open": _safe_float(row.get("open")),
                        "high": _safe_float(row.get("high")),
                        "low": _safe_float(row.get("low")),
                        "close": _safe_float(row.get("close")),
                        "volume": _safe_float(row.get("volume")),
                        "updated_at": now,
                    }
                    await mongo.raw_prices.update_one(
                        {"symbol": symbol, "date": iso_date},
                        {"$set": doc},
                        upsert=True,
                    )
                    inserted_prices += 1
        except Exception:
            pass

        try:
            chip_data = await inst_crawler.get_chip_data(symbol, start.isoformat(), end.isoformat())
            for item in chip_data.get("items", []):
                iso_date = _to_iso(item.get("date"))
                if not iso_date:
                    continue
                doc = {
                    "symbol": symbol,
                    "date": iso_date,
                    "foreign_net_buy": _safe_float(item.get("foreign_net_buy")),
                    "investment_trust_net_buy": _safe_float(item.get("investment_trust_net_buy")),
                    "dealer_net_buy": _safe_float(item.get("dealer_net_buy")),
                    "updated_at": now,
                }
                await mongo.raw_institutional.update_one(
                    {"symbol": symbol, "date": iso_date},
                    {"$set": doc},
                    upsert=True,
                )
                inserted_inst += 1
        except Exception:
            pass

        profile = info_map.get(symbol, {})
        if profile:
            await mongo.raw_industry.update_one(
                {"symbol": symbol},
                {
                    "$set": {
                        "symbol": symbol,
                        "name_zh": profile.get("name_zh") or symbol,
                        "industry": profile.get("industry") or "未知產業",
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
            inserted_industry += 1

    return {
        "symbols": len(symbols),
        "prices": inserted_prices,
        "institutional": inserted_inst,
        "industry": inserted_industry,
    }


async def _load_raw_maps(
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    mongo = await get_mongodb()
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    price_cursor = mongo.raw_prices.find(
        {"symbol": {"$in": symbols}, "date": {"$gte": start_iso, "$lte": end_iso}},
        {"_id": 0},
    )
    inst_cursor = mongo.raw_institutional.find(
        {"symbol": {"$in": symbols}, "date": {"$gte": start_iso, "$lte": end_iso}},
        {"_id": 0},
    )
    industry_cursor = mongo.raw_industry.find({"symbol": {"$in": symbols}}, {"_id": 0})

    price_docs = await price_cursor.to_list(length=None)
    inst_docs = await inst_cursor.to_list(length=None)
    industry_docs = await industry_cursor.to_list(length=None)

    prices_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
    inst_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
    industry_map: dict[str, dict[str, Any]] = {symbol: {"symbol": symbol, "industry": "未知產業", "name_zh": symbol} for symbol in symbols}

    for doc in price_docs:
        symbol = str(doc.get("symbol", "")).upper()
        if symbol in prices_by_symbol:
            prices_by_symbol[symbol].append(doc)
    for doc in inst_docs:
        symbol = str(doc.get("symbol", "")).upper()
        if symbol in inst_by_symbol:
            inst_by_symbol[symbol].append(doc)
    for doc in industry_docs:
        symbol = str(doc.get("symbol", "")).upper()
        if symbol in industry_map:
            industry_map[symbol] = {
                "symbol": symbol,
                "industry": str(doc.get("industry", "") or "未知產業"),
                "name_zh": str(doc.get("name_zh", "") or symbol),
            }

    for docs in prices_by_symbol.values():
        docs.sort(key=lambda item: item.get("date", ""))
    for docs in inst_by_symbol.values():
        docs.sort(key=lambda item: item.get("date", ""))

    return prices_by_symbol, inst_by_symbol, industry_map


def _series_maps(
    prices_by_symbol: dict[str, list[dict[str, Any]]],
    inst_by_symbol: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    close_map: dict[str, dict[str, float]] = {}
    ret_map: dict[str, dict[str, float]] = {}
    flow_map: dict[str, dict[str, float]] = {}

    for symbol, docs in prices_by_symbol.items():
        close_by_date: dict[str, float] = {}
        ret_by_date: dict[str, float] = {}
        prev_close = None
        for doc in docs:
            iso_date = _to_iso(doc.get("date"))
            close = _safe_float(doc.get("close"))
            if not iso_date:
                continue
            close_by_date[iso_date] = close
            if prev_close and prev_close > 0:
                ret_by_date[iso_date] = (close - prev_close) / prev_close
            prev_close = close
        close_map[symbol] = close_by_date
        ret_map[symbol] = ret_by_date

    for symbol, docs in inst_by_symbol.items():
        values: dict[str, float] = {}
        for doc in docs:
            iso_date = _to_iso(doc.get("date"))
            if not iso_date:
                continue
            flow = (
                _safe_float(doc.get("foreign_net_buy"))
                + _safe_float(doc.get("investment_trust_net_buy"))
                + _safe_float(doc.get("dealer_net_buy"))
            )
            values[iso_date] = flow
        flow_map[symbol] = values

    return close_map, ret_map, flow_map


def _aligned_values(map_a: dict[str, float], map_b: dict[str, float], target_date: str, lookback: int) -> tuple[list[str], list[float], list[float]]:
    dates = sorted([d for d in map_a.keys() if d in map_b and d <= target_date])[-lookback:]
    if not dates:
        return [], [], []
    arr_a = [map_a[d] for d in dates]
    arr_b = [map_b[d] for d in dates]
    return dates, arr_a, arr_b


def _build_snapshot_payload(
    symbols: list[str],
    target_date: str,
    close_map: dict[str, dict[str, float]],
    ret_map: dict[str, dict[str, float]],
    flow_map: dict[str, dict[str, float]],
    industry_map: dict[str, dict[str, Any]],
    lookback_days: int,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
) -> dict[str, Any]:
    lead_edges: list[dict[str, Any]] = []
    chip_edges: list[dict[str, Any]] = []
    industry_edges: list[dict[str, Any]] = []
    fusion_acc: dict[str, dict[str, Any]] = {}

    for src in symbols:
        for dst in symbols:
            if src == dst:
                continue
            _, src_ret, dst_ret = _aligned_values(ret_map.get(src, {}), ret_map.get(dst, {}), target_date, lookback_days)
            lag, corr = _best_lag_corr(src_ret, dst_ret, max_lag=5)
            if lag > 0 and abs(corr) >= 0.12:
                edge = {
                    "src": src,
                    "dst": dst,
                    "layer": "lead",
                    "weight": round(float(corr), 4),
                    "abs_weight": round(abs(float(corr)), 4),
                    "lag": lag,
                    "directed": True,
                    "confidence": round(min(1.0, len(src_ret) / 60.0) * abs(float(corr)), 4),
                }
                lead_edges.append(edge)
                fusion_acc.setdefault(_edge_key(src, dst), {"src": src, "dst": dst, "lead": 0.0, "chip": 0.0, "industry": 0.0})
                fusion_acc[_edge_key(src, dst)]["lead"] = float(corr)

            _, src_flow, dst_flow = _aligned_values(flow_map.get(src, {}), flow_map.get(dst, {}), target_date, lookback_days)
            flow_lag, flow_corr = _best_lag_corr(src_flow, dst_flow, max_lag=3)
            if flow_lag > 0 and abs(flow_corr) >= 0.18:
                edge = {
                    "src": src,
                    "dst": dst,
                    "layer": "chip",
                    "weight": round(float(flow_corr), 4),
                    "abs_weight": round(abs(float(flow_corr)), 4),
                    "lag": flow_lag,
                    "directed": True,
                    "confidence": round(min(1.0, len(src_flow) / 45.0) * abs(float(flow_corr)), 4),
                }
                chip_edges.append(edge)
                fusion_acc.setdefault(_edge_key(src, dst), {"src": src, "dst": dst, "lead": 0.0, "chip": 0.0, "industry": 0.0})
                fusion_acc[_edge_key(src, dst)]["chip"] = float(flow_corr)

    for i, src in enumerate(symbols):
        for dst in symbols[i + 1:]:
            src_ind = str(industry_map.get(src, {}).get("industry", "") or "")
            dst_ind = str(industry_map.get(dst, {}).get("industry", "") or "")
            if not src_ind or src_ind != dst_ind:
                continue
            for a, b in ((src, dst), (dst, src)):
                edge = {
                    "src": a,
                    "dst": b,
                    "layer": "industry",
                    "weight": 1.0,
                    "abs_weight": 1.0,
                    "lag": 0,
                    "directed": False,
                    "confidence": 1.0,
                }
                industry_edges.append(edge)
                fusion_acc.setdefault(_edge_key(a, b), {"src": a, "dst": b, "lead": 0.0, "chip": 0.0, "industry": 0.0})
                fusion_acc[_edge_key(a, b)]["industry"] = 1.0

    fusion_edges: list[dict[str, Any]] = []
    for acc in fusion_acc.values():
        lead_weight = acc["lead"]
        chip_weight = acc["chip"]
        industry_weight = acc["industry"]
        total = alpha * lead_weight + beta * chip_weight + gamma * industry_weight
        if abs(total) < 0.05:
            continue
        fusion_edges.append(
            {
                "src": acc["src"],
                "dst": acc["dst"],
                "layer": "fusion",
                "weight": round(float(total), 4),
                "abs_weight": round(abs(float(total)), 4),
                "lag": 0,
                "directed": True,
                "components": {
                    "lead": round(float(lead_weight), 4),
                    "chip": round(float(chip_weight), 4),
                    "industry": round(float(industry_weight), 4),
                },
            }
        )

    node_metrics = _derive_node_metrics(symbols, fusion_edges)
    pagerank = _pagerank(symbols, fusion_edges)
    nodes: list[dict[str, Any]] = []
    for symbol in symbols:
        closes = close_map.get(symbol, {})
        returns = ret_map.get(symbol, {})
        flows = flow_map.get(symbol, {})
        latest_close = closes.get(target_date)
        window_rets = [returns[d] for d in sorted([d for d in returns if d <= target_date])[-20:]]
        window_flows = [flows[d] for d in sorted([d for d in flows if d <= target_date])[-20:]]
        momentum_20 = round(sum(window_rets), 4) if window_rets else 0.0
        flow_strength = round(float(np.mean(window_flows)), 2) if window_flows else 0.0
        info = industry_map.get(symbol, {})
        metrics = node_metrics.get(symbol, {})
        nodes.append(
            {
                "symbol": symbol,
                "name_zh": info.get("name_zh") or symbol,
                "industry": info.get("industry") or "未知產業",
                "latest_close": latest_close,
                "momentum_20": momentum_20,
                "flow_strength": flow_strength,
                "in_weight": round(_safe_float(metrics.get("in_weight")), 4),
                "out_weight": round(_safe_float(metrics.get("out_weight")), 4),
                "weighted_degree": round(_safe_float(metrics.get("weighted_degree")), 4),
                "centrality": round(_safe_float(metrics.get("centrality")), 4),
                "risk_transmission": round(_safe_float(metrics.get("risk_transmission")), 4),
                "pagerank": _safe_float(pagerank.get(symbol), 0.0),
                "community": info.get("industry") or "未知產業",
            }
        )

    n = len(nodes)
    m = len(fusion_edges)
    density = round(m / (n * (n - 1)), 4) if n > 1 else 0.0
    return {
        "date": target_date,
        "nodes": nodes,
        "layers": {
            "lead": lead_edges,
            "chip": chip_edges,
            "industry": industry_edges,
            "fusion": fusion_edges,
        },
        "metrics": {
            "node_count": n,
            "fusion_edge_count": m,
            "density": density,
        },
    }


def _filter_snapshot(snapshot: dict[str, Any], edge_threshold: float) -> dict[str, Any]:
    threshold = max(0.0, min(1.0, float(edge_threshold)))
    layers = snapshot.get("layers", {})
    filtered_layers = {
        layer: [edge for edge in layers.get(layer, []) if _safe_float(edge.get("abs_weight")) >= threshold]
        for layer in ("lead", "chip", "industry", "fusion")
    }
    symbols = [node.get("symbol") for node in snapshot.get("nodes", []) if node.get("symbol")]
    metrics_map = _derive_node_metrics(symbols, filtered_layers.get("fusion", []))
    pagerank = _pagerank(symbols, filtered_layers.get("fusion", []))
    nodes = []
    for node in snapshot.get("nodes", []):
        symbol = node.get("symbol")
        updated = dict(node)
        stats = metrics_map.get(symbol, {})
        updated["in_weight"] = round(_safe_float(stats.get("in_weight")), 4)
        updated["out_weight"] = round(_safe_float(stats.get("out_weight")), 4)
        updated["weighted_degree"] = round(_safe_float(stats.get("weighted_degree")), 4)
        updated["centrality"] = round(_safe_float(stats.get("centrality")), 4)
        updated["risk_transmission"] = round(_safe_float(stats.get("risk_transmission")), 4)
        updated["pagerank"] = _safe_float(pagerank.get(symbol), 0.0)
        nodes.append(updated)

    n = len(nodes)
    m = len(filtered_layers.get("fusion", []))
    metrics = dict(snapshot.get("metrics", {}))
    metrics.update(
        {
            "node_count": n,
            "fusion_edge_count": m,
            "density": round(m / (n * (n - 1)), 4) if n > 1 else 0.0,
            "edge_threshold": threshold,
        }
    )
    return {
        "date": snapshot.get("date"),
        "watchlist_hash": snapshot.get("watchlist_hash"),
        "symbols": snapshot.get("symbols", []),
        "nodes": nodes,
        "layers": filtered_layers,
        "metrics": metrics,
    }


async def _upsert_snapshot(
    snapshot: dict[str, Any],
    feature_nodes: list[dict[str, Any]],
    feature_edges: dict[str, list[dict[str, Any]]],
) -> None:
    mongo = await get_mongodb()
    now = datetime.utcnow()
    watchlist_hash = snapshot.get("watchlist_hash")
    date_value = snapshot.get("date")

    await mongo.feature_nodes_daily.update_one(
        {"watchlist_hash": watchlist_hash, "date": date_value},
        {"$set": {"watchlist_hash": watchlist_hash, "date": date_value, "nodes": feature_nodes, "updated_at": now}},
        upsert=True,
    )
    await mongo.feature_edges_daily.update_one(
        {"watchlist_hash": watchlist_hash, "date": date_value},
        {"$set": {"watchlist_hash": watchlist_hash, "date": date_value, "layers": feature_edges, "updated_at": now}},
        upsert=True,
    )
    await mongo.graph_snapshots.update_one(
        {"watchlist_hash": watchlist_hash, "date": date_value},
        {"$set": {**snapshot, "updated_at": now}},
        upsert=True,
    )


async def build_watchlist_graph(
    symbols: list[str],
    target_date: str | date | None = None,
    lookback_days: int = 60,
    force_ingest: bool = True,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
) -> dict[str, Any]:
    symbols = _normalize_symbols(symbols)
    if len(symbols) < 2:
        raise ValueError("觀察池至少需 2 檔股票")

    target = _parse_date(target_date, fallback=date.today())
    ingest_start = target - timedelta(days=max(lookback_days * 3, 180))
    if force_ingest:
        await ingest_watchlist_raw(symbols, ingest_start, target)

    prices_by_symbol, inst_by_symbol, industry_map = await _load_raw_maps(symbols, ingest_start, target)
    close_map, ret_map, flow_map = _series_maps(prices_by_symbol, inst_by_symbol)
    payload = _build_snapshot_payload(
        symbols=symbols,
        target_date=target.isoformat(),
        close_map=close_map,
        ret_map=ret_map,
        flow_map=flow_map,
        industry_map=industry_map,
        lookback_days=lookback_days,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
    )
    snapshot = {
        "watchlist_hash": _watchlist_hash(symbols),
        "symbols": symbols,
        "date": target.isoformat(),
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        **payload,
        "created_at": datetime.utcnow(),
    }
    await _upsert_snapshot(snapshot, payload["nodes"], payload["layers"])
    return snapshot


async def get_watchlist_snapshot(
    symbols: list[str],
    target_date: str | date | None = None,
    edge_threshold: float = 0.35,
    lookback_days: int = 60,
) -> dict[str, Any]:
    symbols = _normalize_symbols(symbols)
    target = _parse_date(target_date, fallback=date.today())
    mongo = await get_mongodb()
    await ensure_graph_indexes(mongo)

    watch_hash = _watchlist_hash(symbols)
    snapshot = await mongo.graph_snapshots.find_one(
        {"watchlist_hash": watch_hash, "date": target.isoformat()},
        {"_id": 0},
    )
    if not snapshot:
        snapshot = await build_watchlist_graph(symbols, target, lookback_days=lookback_days, force_ingest=True)
    return _filter_snapshot(snapshot, edge_threshold=edge_threshold)


async def get_watchlist_timeline(
    symbols: list[str],
    start_date: str | date,
    end_date: str | date,
    edge_threshold: float = 0.35,
    lookback_days: int = 60,
) -> dict[str, Any]:
    symbols = _normalize_symbols(symbols)
    if len(symbols) < 2:
        raise ValueError("觀察池至少需 2 檔股票")
    start = _parse_date(start_date)
    end = _parse_date(end_date, fallback=start)
    if end < start:
        start, end = end, start

    await ingest_watchlist_raw(symbols, start - timedelta(days=max(lookback_days * 2, 120)), end)
    snapshots: list[dict[str, Any]] = []
    cursor_day = start
    while cursor_day <= end:
        try:
            snapshot = await get_watchlist_snapshot(
                symbols=symbols,
                target_date=cursor_day,
                edge_threshold=edge_threshold,
                lookback_days=lookback_days,
            )
            if snapshot.get("nodes"):
                snapshots.append(snapshot)
        except Exception:
            pass
        cursor_day += timedelta(days=1)

    # 去重（同日期只留一筆）
    unique: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        snapshot_date = str(snapshot.get("date", ""))
        if snapshot_date:
            unique[snapshot_date] = snapshot
    ordered = [unique[k] for k in sorted(unique.keys())]
    return {
        "watchlist_hash": _watchlist_hash(symbols),
        "symbols": symbols,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "edge_threshold": max(0.0, min(1.0, float(edge_threshold))),
        "items": ordered,
    }


async def get_watchlist_alerts(
    symbols: list[str],
    edge_threshold: float = 0.35,
) -> dict[str, Any]:
    symbols = _normalize_symbols(symbols)
    watch_hash = _watchlist_hash(symbols)
    mongo = await get_mongodb()

    cursor = mongo.graph_snapshots.find(
        {"watchlist_hash": watch_hash},
        {"_id": 0},
    ).sort("date", -1).limit(2)
    latest_two = await cursor.to_list(length=2)
    if not latest_two:
        return {"watchlist_hash": watch_hash, "items": []}

    latest = _filter_snapshot(latest_two[0], edge_threshold)
    previous = _filter_snapshot(latest_two[1], edge_threshold) if len(latest_two) > 1 else None
    alerts: list[dict[str, Any]] = []

    if previous:
        prev_map = {node["symbol"]: node for node in previous.get("nodes", [])}
        for node in latest.get("nodes", []):
            symbol = node.get("symbol")
            prev = prev_map.get(symbol)
            if not prev:
                continue
            prev_deg = _safe_float(prev.get("weighted_degree"), 0.0)
            curr_deg = _safe_float(node.get("weighted_degree"), 0.0)
            if prev_deg > 0 and (prev_deg - curr_deg) / prev_deg >= 0.35:
                alerts.append(
                    {
                        "type": "core_weakening",
                        "symbol": symbol,
                        "message": f"{symbol} 關聯度顯著下降（{round((prev_deg - curr_deg) / prev_deg * 100, 1)}%）",
                        "severity": "warning",
                        "date": latest.get("date"),
                    }
                )

    sector_counts: dict[str, int] = {}
    for node in latest.get("nodes", []):
        sector = str(node.get("industry", "未知產業"))
        centrality = _safe_float(node.get("centrality"))
        if centrality >= 0.6:
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
    for sector, count in sector_counts.items():
        if count >= 2:
            alerts.append(
                {
                    "type": "community_hotspot",
                    "symbol": sector,
                    "message": f"{sector} 社群出現 {count} 檔高中心性節點",
                    "severity": "info",
                    "date": latest.get("date"),
                }
            )

    await mongo.graph_alerts.update_one(
        {"watchlist_hash": watch_hash, "date": latest.get("date")},
        {"$set": {"watchlist_hash": watch_hash, "date": latest.get("date"), "items": alerts, "created_at": datetime.utcnow()}},
        upsert=True,
    )
    return {"watchlist_hash": watch_hash, "date": latest.get("date"), "items": alerts}
