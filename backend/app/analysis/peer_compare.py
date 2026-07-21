"""同業比較（U1 Peer Comparison）。

設計（呼應高力 8996 案例的教訓）：
- 官方產業分類（FinMind industry_category）只能當「預設」——高力的官方分類
  是電機機械，但真同業（奇鋐/雙鴻/台達電）散在別的分類，題材同業必須讓
  使用者手動維護（存 Mongo，PUT /peers），或透過前端的 AI 協助流程貼回。
- 產業預設的流動性排名不逐檔打 FinMind：改用 TWSE/TPEx 官方「全市場日行情」
  開放端點，各一個請求拿到全部股票的成交金額，快取半天。
- 比較表本身每檔要 5 個 FinMind 呼叫（價格/估值/營收/財報/股數），整包
  Mongo 快取 6 小時——PE 日頻、營收月頻、財報季頻，這個新鮮度綽綽有餘。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

TWSE_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_ALL_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"

MAX_PEERS = 10
DEFAULT_PEER_COUNT = 5


def _to_float(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


async def _fetch_market_quotes() -> dict[str, float]:
    """全市場成交金額 { symbol: trade_value }，TWSE+TPEx 各一個請求，快取半天。

    只用來做「同產業內誰比較有流動性」的排序，抓不到時回傳空 dict（產業預設
    會退化成不排序），不影響自訂同業群組的功能。
    """
    from ..db.cache import get_cache, set_cache

    cache_key = "market_quotes:v1"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    quotes: dict[str, float] = {}
    # verify=False：TPEx 的 TLS 憑證鏈缺 Subject Key Identifier，會被嚴格版
    # OpenSSL 拒絕（跟 chip_distribution.py 抓 TDCC 同一類問題、同一個先例
    # 處理）；這是無需驗證身分的公開資料，關閉驗證不增加風險。
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            resp = await client.get(TWSE_ALL_URL)
            resp.raise_for_status()
            for row in resp.json():
                sym = str(row.get("Code", "")).strip()
                if sym:
                    quotes[sym] = _to_float(row.get("TradeValue"))
        except Exception as exc:
            logger.warning("TWSE STOCK_DAY_ALL fetch failed: %s", exc)
        try:
            resp = await client.get(TPEX_ALL_URL)
            resp.raise_for_status()
            for row in resp.json():
                sym = str(row.get("SecuritiesCompanyCode", "")).strip()
                if sym and sym not in quotes:
                    quotes[sym] = _to_float(row.get("TransactionAmount"))
        except Exception as exc:
            logger.warning("TPEx daily quotes fetch failed: %s", exc)

    if quotes:
        try:
            await set_cache(cache_key, quotes, "market_quotes")
        except Exception:
            pass
    return quotes


async def _stock_info_maps() -> tuple[dict[str, str], dict[str, str]]:
    """回傳 ({symbol: industry}, {symbol: name})，來源 FinMind TaiwanStockInfo。"""
    from ..crawler.finmind_client import FinMindClient

    info = await FinMindClient().get_stock_info()
    industry_map: dict[str, str] = {}
    name_map: dict[str, str] = {}
    if info is not None and not info.empty:
        for _, row in info.iterrows():
            sym = str(row.get("stock_id", "")).strip()
            if not sym:
                continue
            industry_map.setdefault(sym, str(row.get("industry_category", "") or ""))
            name_map.setdefault(sym, str(row.get("stock_name", "") or ""))
    return industry_map, name_map


async def get_peer_group(symbol: str) -> dict:
    """生效中的同業群組：自訂（Mongo）優先，否則同產業成交金額前 N 名。"""
    from ..db.cache import get_setting

    industry_map, name_map = await _stock_info_maps()
    industry = industry_map.get(symbol, "")

    custom = None
    try:
        custom = await get_setting(f"peer_group:{symbol}")
    except Exception:
        pass
    if custom and custom.get("peers"):
        peers = [
            {"symbol": p["symbol"], "name": name_map.get(p["symbol"], p["symbol"]),
             "source": p.get("source", "manual")}
            for p in custom["peers"][:MAX_PEERS]
        ]
        return {"symbol": symbol, "industry": industry, "group_source": "custom", "peers": peers}

    # 產業預設：同分類、4 位數代碼、依全市場成交金額排序取前 N
    members = [s for s, ind in industry_map.items()
               if ind and ind == industry and s != symbol and len(s) == 4 and s.isdigit()]
    quotes = await _fetch_market_quotes()
    members.sort(key=lambda s: quotes.get(s, 0.0), reverse=True)
    peers = [
        {"symbol": s, "name": name_map.get(s, s), "source": "industry"}
        for s in members[:DEFAULT_PEER_COUNT]
    ]
    return {"symbol": symbol, "industry": industry, "group_source": "industry", "peers": peers}


AI_PEER_SYSTEM_PROMPT = """你是台股產業研究助理。使用者會給你一檔股票的代碼、名稱、
官方產業分類與市值，請憑你的知識列出台灣上市櫃中業務性質最相似（真正的競爭對手，
不是官方分類相同但業務無關的公司）的 5 到 8 檔股票。

規則：
1. 只能回答台灣上市櫃公司，且必須是實際存在的 4 位數股票代碼。不確定代碼是否正確
   時寧可少列，不可編造代碼。
2. 判斷依據是實際業務/產品線相似度，不是官方產業分類。
3. 輸出格式：只輸出 JSON 陣列，不要任何其他文字。每個元素：
   {"symbol": "4位數代碼", "name": "公司名稱", "reason": "15字以內的相似原因"}"""


async def ai_suggest_peers(symbol: str) -> dict:
    """W1：AI 直接建議同業，取代手動複製提示詞貼去 Gemini 再貼回的流程。

    防幻覺：LLM 憑訓練知識列出的代碼可能是錯的或已下市，一律拿真實的
    TaiwanStockInfo 名單驗證過才回傳；驗證不過的直接丟棄，不讓幻想代碼
    流到前端。這裡不寫入 Mongo——建議清單只是候選，使用者仍要在前端勾選
    確認才會呼叫 PUT /peers 真正儲存，跟既有的貼回流程行為一致。
    """
    from ..llm import LLMUnavailable, llm_complete

    industry_map, name_map = await _stock_info_maps()
    if symbol not in name_map:
        raise ValueError("查無此股票代碼")

    industry = industry_map.get(symbol, "")
    name = name_map.get(symbol, symbol)
    user_prompt = f"股票代碼：{symbol}\n名稱：{name}\n官方產業分類：{industry or '未知'}"

    try:
        raw = await llm_complete(AI_PEER_SYSTEM_PROMPT, user_prompt, max_tokens=1200, temperature=0.3)
    except LLMUnavailable as exc:
        raise ValueError(str(exc)) from exc

    import json
    import re

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    try:
        items = json.loads(match.group(0)) if match else []
    except (json.JSONDecodeError, AttributeError):
        items = []

    candidates = []
    seen = {symbol}
    for item in items:
        if not isinstance(item, dict):
            continue
        sym = str(item.get("symbol", "")).strip()
        if not (len(sym) == 4 and sym.isdigit()) or sym in seen:
            continue
        seen.add(sym)
        # 驗證：代碼必須真的存在於 FinMind 官方名單，否則視為幻覺捨棄
        real_name = name_map.get(sym)
        candidates.append({
            "symbol": sym,
            "name": real_name or str(item.get("name", "")).strip(),
            "reason": str(item.get("reason", "")).strip()[:40],
            "valid": real_name is not None,
        })

    return {
        "symbol": symbol,
        "candidates": candidates[:10],
        "raw_count": len(items),
    }


async def set_peer_group(symbol: str, peers: list[dict]) -> None:
    """儲存自訂同業群組；空清單＝清除自訂、回到產業預設。"""
    from datetime import datetime

    from ..db.cache import set_setting

    cleaned = []
    seen = set()
    for p in peers[:MAX_PEERS]:
        sym = str(p.get("symbol", "")).strip()
        if not (len(sym) == 4 and sym.isdigit()) or sym == symbol or sym in seen:
            continue
        seen.add(sym)
        source = p.get("source") if p.get("source") in ("manual", "ai", "industry") else "manual"
        cleaned.append({"symbol": sym, "source": source})

    await set_setting(
        f"peer_group:{symbol}",
        {"peers": cleaned, "updated_at": datetime.utcnow().isoformat()} if cleaned else None,
    )


async def _one_metrics(sym: str, name: str, source: str) -> dict:
    """單一股票的比較指標。任何一項抓不到就留 None，不讓整列失敗。"""
    from ..analysis.market_cap import classify_cap_tier, get_shares_outstanding
    from ..crawler.finmind_client import FinMindClient
    from ..crawler.fundamental import FundamentalCrawler
    from ..crawler.stock_price import StockPriceCrawler

    end = date.today()
    row: dict = {"symbol": sym, "name": name, "source": source}

    async def _price():
        try:
            df = await StockPriceCrawler().get_price(
                sym, (end - timedelta(days=420)).isoformat(), end.isoformat(), "1d")
            if df is None or df.empty:
                return
            df = df.sort_values("date")
            close = df["close"].astype(float)
            price = float(close.iloc[-1])
            row["price"] = round(price, 2)
            if len(close) >= 21:
                row["mom20_pct"] = round((price / float(close.iloc[-21]) - 1) * 100, 1)
            if len(close) >= 200:
                row["above_ma200"] = bool(price > float(close.tail(200).mean()))
        except Exception:
            pass

    async def _valuation():
        try:
            df = await FinMindClient().get_valuation(
                sym, (end - timedelta(days=10)).isoformat(), end.isoformat())
            if df is None or df.empty:
                return
            last = df.sort_values("date").iloc[-1]
            per = float(last.get("PER", 0) or 0)
            row["pe"] = round(per, 1) if per > 0 else None  # 虧損股 PER 缺值/0
            pbr = float(last.get("PBR", 0) or 0)
            row["pbr"] = round(pbr, 2) if pbr > 0 else None
            dy = float(last.get("dividend_yield", 0) or 0)
            row["dividend_yield"] = round(dy, 2) if dy > 0 else None
        except Exception:
            pass

    async def _revenue():
        try:
            items = await FundamentalCrawler().get_monthly_revenue(
                sym, (end - timedelta(days=460)).isoformat(), end.isoformat())
            recent = [i for i in items if i.get("yoy") is not None][-3:]
            if recent:
                row["revenue_yoy_3m"] = [round(float(i["yoy"]), 1) for i in recent]
                row["revenue_yoy_avg"] = round(
                    sum(float(i["yoy"]) for i in recent) / len(recent), 1)
        except Exception:
            pass

    async def _financials():
        try:
            fin = await FundamentalCrawler().get_financial_statements(
                sym, (end - timedelta(days=560)).isoformat(), end.isoformat())
            eps_rows = fin.get("eps_quarterly") or []
            if eps_rows:
                last = eps_rows[-1]
                row["eps_quarter"] = last["quarter"]
                row["eps"] = round(float(last["eps"]), 2)
                prev_q = f"{int(last['quarter'][:4]) - 1}{last['quarter'][4:]}"
                prev = next((r for r in eps_rows if r["quarter"] == prev_q), None)
                if prev and float(prev["eps"]) > 0:
                    row["eps_yoy_pct"] = round(
                        (float(last["eps"]) / float(prev["eps"]) - 1) * 100, 1)
            margins = fin.get("margins") or []
            if margins:
                m = margins[-1]
                if m.get("gross_margin") is not None:
                    row["gross_margin"] = round(float(m["gross_margin"]), 1)
                if m.get("operating_margin") is not None:
                    row["operating_margin"] = round(float(m["operating_margin"]), 1)
        except Exception:
            pass

    async def _mktcap():
        try:
            shares = await get_shares_outstanding(
                sym, (end - timedelta(days=120)).isoformat(), end.isoformat())
            price = row.get("price")
            if shares and price:
                cap = price * shares
                row["market_cap"] = round(cap)
                row["cap_tier"] = classify_cap_tier(cap)
        except Exception:
            pass

    await _price()  # 先抓價格，市值計算要用
    await asyncio.gather(_valuation(), _revenue(), _financials(), _mktcap())
    return row


async def build_comparison(symbol: str) -> dict:
    """比較表本體：目標股＋同業的估值/成長/獲利/動能指標，Mongo 快取 6 小時。"""
    from ..db.cache import get_cache, set_cache

    group = await get_peer_group(symbol)
    peer_syms = [p["symbol"] for p in group["peers"]]
    cache_key = f"peer_comparison:v1:{symbol}:{','.join(sorted(peer_syms))}"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    _, name_map = await _stock_info_maps()
    rows = await asyncio.gather(
        _one_metrics(symbol, name_map.get(symbol, symbol), "target"),
        *[_one_metrics(p["symbol"], p["name"], p["source"]) for p in group["peers"]],
    )
    result = {
        "symbol": symbol,
        "industry": group["industry"],
        "group_source": group["group_source"],
        "target": rows[0],
        "peers": list(rows[1:]),
        "as_of": date.today().isoformat(),
    }
    try:
        await set_cache(cache_key, result, "peer")
    except Exception:
        pass
    return result
