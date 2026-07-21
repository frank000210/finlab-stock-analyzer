"""自然語言選股（W8）。

呼應先前手動的「screen_peers.py」一次性腳本（找高力 8996 的合理估值替代
品時寫的）——這裡把那套人工流程（LLM 解析條件 → 選候選池 → 逐檔抓指標 →
套用數字篩選）變成網站的正式功能，而不是每次要重新寫腳本。

設計：
1. LLM 只負責把自然語言解析成「結構化篩選條件」（產業關鍵字/PE/營收年增
   門檻），不負責選股本身——實際篩選是用網站既有數據跑數字比較，LLM 沒有
   機會憑空生出一檔股票。
2. 候選池用官方產業分類關鍵字比對縮小範圍，再依全市場成交金額（複用 U1
   peer_compare 的 market_quotes 快取）取前 N 檔，避免對全市場 2000+ 檔
   逐一呼叫 FinMind——成本與時間都扛不住。這代表結果是「候選池裡最符合
   條件的」，不是嚴格意義的全市場掃描，UI 必須誠實揭露候選池大小。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 30

SYSTEM_PROMPT = """你是台股選股條件解析助理。使用者會用自然語言描述想找的股票條件，
你要把它轉成結構化 JSON，不做最終選股判斷（篩選由系統用真實數據執行）。

規則：
1. 只輸出 JSON，不要其他文字。
2. 欄位：
   {"industry_keywords": ["關鍵字1", "關鍵字2"],
    "candidate_symbols": [{"symbol": "4位數代碼", "name": "公司名稱"}, ...],
    "pe_max": 數字或null, "pe_min": 數字或null, "revenue_yoy_min": 數字或null,
    "description": "20字以內覆述使用者的需求"}
3. industry_keywords 是用來比對台灣「官方」產業分類與公司名稱的關鍵字（例如
   「電子零組件」「半導體」），若使用者沒有指定產業/題材，回傳空陣列。
4. candidate_symbols 很重要：官方產業分類通常抓不到題材股（例如「散熱」
   不是官方分類，但奇鋐/雙鴻/建準是實際的散熱股）。請憑你的知識直接列出
   10-20 檔你認為最符合使用者描述的台灣上市櫃公司代碼與名稱，不確定代碼
   是否正確時寧可少列，不可編造代碼（系統會逐一驗證代碼是否真實存在）。
   若使用者的描述純粹是數字門檻、沒有產業/題材字眼，回傳空陣列即可。
5. pe_max/pe_min/revenue_yoy_min 只在使用者明確提到數字門檻時才填，沒提到
   就是 null，不要自己猜一個門檻。"""


async def parse_query(query: str) -> dict:
    from ..llm import llm_complete

    raw = await llm_complete(SYSTEM_PROMPT, query, max_tokens=1200, temperature=0.2)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        parsed = json.loads(match.group(0)) if match else {}
    except (json.JSONDecodeError, AttributeError):
        parsed = {}

    candidate_symbols = []
    seen = set()
    for item in (parsed.get("candidate_symbols") or []):
        if not isinstance(item, dict):
            continue
        sym = str(item.get("symbol", "")).strip()
        if len(sym) == 4 and sym.isdigit() and sym not in seen:
            seen.add(sym)
            candidate_symbols.append(sym)

    return {
        "industry_keywords": [str(k).strip() for k in (parsed.get("industry_keywords") or []) if str(k).strip()][:6],
        "candidate_symbols": candidate_symbols[:20],
        "pe_max": _to_num(parsed.get("pe_max")),
        "pe_min": _to_num(parsed.get("pe_min")),
        "revenue_yoy_min": _to_num(parsed.get("revenue_yoy_min")),
        "description": str(parsed.get("description", "")).strip()[:60],
    }


def _to_num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _match_row(row: dict, criteria: dict) -> bool:
    if criteria["pe_max"] is not None and (row.get("pe") is None or row["pe"] > criteria["pe_max"]):
        return False
    if criteria["pe_min"] is not None and (row.get("pe") is None or row["pe"] < criteria["pe_min"]):
        return False
    if criteria["revenue_yoy_min"] is not None:
        yoy = row.get("revenue_yoy_avg")
        if yoy is None or yoy < criteria["revenue_yoy_min"]:
            return False
    return True


async def run_screener(query: str, expand: bool = False) -> dict:
    """自然語言選股本體。快取 6 小時（跟 peer_compare 同節奏），key 為查詢文字。

    X10：expand=True 時把候選池上限翻倍——第一輪候選池太窄找不到符合條件
    的股票時，前端可以直接要求擴大範圍重查，不用逼使用者換句話重問。
    """
    from datetime import date

    from .peer_compare import _fetch_market_quotes, _one_metrics, _stock_info_maps
    from ..db.cache import get_cache, set_cache

    normalized = query.strip()
    cache_key = f"nl_screener:v1:{normalized}:{'expand' if expand else 'std'}:{date.today().isoformat()}"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return {**cached, "cached": True}
    except Exception:
        pass

    max_candidates = MAX_CANDIDATES * 2 if expand else MAX_CANDIDATES
    criteria = await parse_query(normalized)
    industry_map, name_map = await _stock_info_maps()

    keywords = criteria["industry_keywords"]
    keyword_matches = [
        s for s, ind in industry_map.items()
        if len(s) == 4 and s.isdigit()
        and (any(kw in ind for kw in keywords) or any(kw in name_map.get(s, "") for kw in keywords))
    ] if keywords else []

    # LLM 建議的候選代碼：先驗證真的存在於官方名單，防止幻覺代碼流入。
    # 題材股（如「散熱」）官方分類通常抓不到，這批候選是主要來源；
    # 官方分類比對到的（keyword_matches）則作為補充，兩者聯集去重。
    llm_candidates = [s for s in criteria["candidate_symbols"] if s in name_map]

    quotes = await _fetch_market_quotes()

    if not keywords and not llm_candidates:
        # 使用者純粹給數字門檻、沒有產業/題材字眼：退化成全市場依成交金額
        # 取前 N，而非逐檔硬掃全市場
        candidate_syms = sorted(
            (s for s in industry_map if len(s) == 4 and s.isdigit()),
            key=lambda s: quotes.get(s, 0.0), reverse=True,
        )[:max_candidates]
    else:
        # LLM 候選一律保留（題材股常是低成交金額的中小型股，跟官方分類
        # 比對到的股票混在一起依成交金額排序會被擠掉），剩餘名額才給
        # 依成交金額排序的官方分類比對結果補滿。
        remaining = max(0, max_candidates - len(llm_candidates))
        fill = sorted(
            (s for s in keyword_matches if s not in llm_candidates),
            key=lambda s: quotes.get(s, 0.0), reverse=True,
        )[:remaining]
        candidate_syms = llm_candidates + fill

    rows = await asyncio.gather(
        *[_one_metrics(s, name_map.get(s, s), "screener") for s in candidate_syms]
    )
    matched = [r for r in rows if _match_row(r, criteria)]
    matched.sort(key=lambda r: (r.get("pe") is None, r.get("pe") or 0))

    result = {
        "query": normalized,
        "criteria": criteria,
        "candidate_pool_size": len(candidate_syms),
        "candidate_pool_max": max_candidates,
        "expanded": expand,
        "matched": matched,
        "matched_count": len(matched),
        "as_of": date.today().isoformat(),
        "cached": False,
    }
    try:
        await set_cache(cache_key, result, "peer")
    except Exception:
        pass
    return result
