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


def _extract_positive_pe(raw) -> float | None:
    try:
        val = float(raw)
        return round(val, 1) if val > 0 else None
    except (TypeError, ValueError):
        return None


async def _prescreen_candidates(
    candidate_syms: list[str],
    criteria: dict,
    *,
    today=None,
) -> list[str]:
    """第一階段零額度初篩：直接讀本地 od_valuation / md_valuation 與 od_revenue / md_revenue，
    剔除確定不符 PE 或營收年增門檻的候選股；庫內查無資料或不夠新的標的保留進第二階段，
    不犧牲召回率。Mongo 不可用或逾時時安全回傳完整候選池。
    """
    from datetime import date, timedelta

    from ..data import db_reader as dr
    from ..data import open_data as od
    from ..data import stock_store as st

    if not candidate_syms:
        return []
    has_pe = criteria.get("pe_max") is not None or criteria.get("pe_min") is not None
    has_yoy = criteria.get("revenue_yoy_min") is not None
    if not has_pe and not has_yoy:
        return list(candidate_syms)

    ref_today = today or date.today()
    survivors = list(candidate_syms)

    async def _run() -> list[str]:
        nonlocal survivors
        od_db = await od._db()
        st_db = await st._db()

        # 1. 本地 PE 初篩（優先 od_valuation，缺漏補查 md_valuation）
        if has_pe and survivors:
            since_val = (ref_today - timedelta(days=14)).isoformat()
            od_val_docs = await od_db["od_valuation"].find(
                {"symbol": {"$in": survivors}, "date": {"$gte": since_val}},
                {"_id": 0, "symbol": 1, "date": 1, "pe": 1},
            ).to_list(length=None)
            latest_val: dict[str, tuple[str, float | None]] = {}
            for doc in od_val_docs:
                sym = str(doc.get("symbol", "")).upper()
                d_str = str(doc.get("date", ""))[:10]
                if not sym or not d_str:
                    continue
                if sym not in latest_val or d_str >= latest_val[sym][0]:
                    latest_val[sym] = (d_str, _extract_positive_pe(doc.get("pe")))

            missing_val = [s for s in survivors if s not in latest_val]
            if missing_val:
                md_val_docs = await st_db["md_valuation"].find(
                    {"symbol": {"$in": missing_val}, "date": {"$gte": since_val}},
                    {"_id": 0, "symbol": 1, "date": 1, "PER": 1},
                ).to_list(length=None)
                for doc in md_val_docs:
                    sym = str(doc.get("symbol", "")).upper()
                    d_str = str(doc.get("date", ""))[:10]
                    if not sym or not d_str:
                        continue
                    if sym not in latest_val or d_str >= latest_val[sym][0]:
                        latest_val[sym] = (d_str, _extract_positive_pe(doc.get("PER")))

            pe_max = criteria.get("pe_max")
            pe_min = criteria.get("pe_min")
            next_survivors = []
            for sym in survivors:
                if sym not in latest_val:
                    next_survivors.append(sym)  # 本地無紀錄，保留進第二階段補查
                    continue
                pe = latest_val[sym][1]
                if pe_max is not None and (pe is None or pe > pe_max):
                    continue
                if pe_min is not None and (pe is None or pe < pe_min):
                    continue
                next_survivors.append(sym)
            survivors = next_survivors

        # 2. 本地營收 YoY 初篩（優先 od_revenue 官方 yoy，不足補查 md_revenue）
        if has_yoy and survivors:
            yoy_min = criteria["revenue_yoy_min"]
            expected_rev_iso = dr.expected_latest_revenue_date(ref_today).isoformat()
            ym_since_y, ym_since_m = dr._shift_month(ref_today.year, ref_today.month, -8)
            ym_since = f"{ym_since_y:04d}-{ym_since_m:02d}"

            od_rev_docs = await od_db["od_revenue"].find(
                {"symbol": {"$in": survivors}, "ym": {"$gte": ym_since}},
                {"_id": 0, "symbol": 1, "ym": 1, "yoy": 1},
            ).to_list(length=None)
            od_by_sym: dict[str, list[tuple[str, float]]] = {}
            for doc in od_rev_docs:
                sym = str(doc.get("symbol", "")).upper()
                ym = str(doc.get("ym", ""))[:7]
                yoy_val = _to_num(doc.get("yoy"))
                if sym and ym and yoy_val is not None:
                    od_by_sym.setdefault(sym, []).append((ym, yoy_val))

            known_yoy_avg: dict[str, float] = {}
            for sym, pairs in od_by_sym.items():
                pairs.sort(key=lambda x: x[0])
                latest_fm = dr.ym_to_finmind_date(pairs[-1][0])
                if len(pairs) >= 3 and latest_fm and latest_fm >= expected_rev_iso:
                    recent3 = [v for _, v in pairs[-3:]]
                    known_yoy_avg[sym] = round(sum(recent3) / 3.0, 1)

            missing_rev = [s for s in survivors if s not in known_yoy_avg]
            if missing_rev:
                rev_since = (ref_today - timedelta(days=460)).isoformat()
                md_rev_docs = await st_db["md_revenue"].find(
                    {"symbol": {"$in": missing_rev}, "date": {"$gte": rev_since}},
                    {"_id": 0, "symbol": 1, "date": 1, "revenue": 1, "revenue_year": 1, "revenue_month": 1},
                ).to_list(length=None)
                md_by_sym: dict[str, list[dict]] = {}
                for doc in md_rev_docs:
                    sym = str(doc.get("symbol", "")).upper()
                    if sym:
                        md_by_sym.setdefault(sym, []).append(doc)
                for sym, docs in md_by_sym.items():
                    docs.sort(key=lambda d: str(d.get("date", "")))
                    latest_d = str(docs[-1].get("date", ""))[:10]
                    if not latest_d or latest_d < expected_rev_iso:
                        continue
                    rev_map: dict[tuple[int, int], float] = {}
                    for d in docs:
                        y, m, r = int(d.get("revenue_year") or 0), int(d.get("revenue_month") or 0), _to_num(d.get("revenue"))
                        if y and m and r is not None:
                            rev_map[(y, m)] = r
                    yoys: list[float] = []
                    for d in docs:
                        y, m, r = int(d.get("revenue_year") or 0), int(d.get("revenue_month") or 0), _to_num(d.get("revenue"))
                        prev = rev_map.get((y - 1, m))
                        if y and m and r is not None and prev and prev > 0:
                            yoys.append((r - prev) / prev * 100.0)
                    if len(yoys) >= 3:
                        recent3 = yoys[-3:]
                        known_yoy_avg[sym] = round(sum(recent3) / 3.0, 1)

            survivors = [
                sym for sym in survivors
                if sym not in known_yoy_avg or known_yoy_avg[sym] >= yoy_min
            ]

        return survivors

    try:
        return await asyncio.wait_for(_run(), timeout=dr.DB_READ_TIMEOUT_SEC)
    except Exception as exc:  # noqa: BLE001
        logger.debug("nl_screener prescreen skipped, falling back to stage 2: %s", exc)
        return list(candidate_syms)


async def run_screener(query: str, expand: bool = False) -> dict:
    """自然語言選股本體。快取 6 小時（跟 peer_compare 同節奏），key 為查詢文字。

    兩階段省額度設計：
    1. 第一階段優先用本地 Mongo（od_valuation / md_valuation / od_revenue / md_revenue）
       做零額度初篩，先淘汰確定不符門檻的候選股。
    2. 第二階段僅對通過或庫內缺資料的標的補抓指標，且關閉選股沒用到的市值查詢。

    X10：expand=True 時把候選池上限翻倍——第一輪候選池太窄找不到符合條件
    的股票時，前端可以直接要求擴大範圍重查，不用逼使用者換句話重問。
    """
    from datetime import date

    from .peer_compare import _fetch_market_quotes, _one_metrics, _safe_get_cache, _safe_set_cache, _stock_info_maps

    normalized = query.strip()
    cache_key = f"nl_screener:v1:{normalized}:{'expand' if expand else 'std'}:{date.today().isoformat()}"
    cached = await _safe_get_cache(cache_key)
    if cached:
        return {**cached, "cached": True}

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

    # 第一階段：零額度本地 DB 預篩
    stage2_syms = await _prescreen_candidates(candidate_syms, criteria)

    # 第二階段：僅對通過或本地缺資料的標的補抓指標；AI 選股不顯示市值，關閉市值查詢省額度
    rows = await asyncio.gather(
        *[
            _one_metrics(
                s,
                name_map.get(s, s),
                "screener",
                include_market_cap=False,
                include_financials=True,
            )
            for s in stage2_syms
        ]
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
    await _safe_set_cache(cache_key, result, "peer")
    return result
