"""新聞摘要與多空判讀（W4）。

跟 W2 個股 AI 摘要同樣的防幻覺原則：LLM 只能總結「已經抓到的標題清單」，
不得杜撰未列出的新聞內容或事件。輸入只給標題／來源／日期，不給全文（社群
熱度抓取本來就只存標題），天然限制了 LLM 編造細節的空間。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是台股新聞輿情助理。使用者會給你一檔股票近期的 PTT 討論、
新聞、財經媒體報導標題清單與統計數據。

嚴格規則：
1. 只能根據使用者提供的標題與統計數據做總結，不得杜撰任何未列出的新聞內容、
   事件細節或數字。標題本身可能有誇大或聳動用語，摘要時不要照單全收。
2. 不得提供投資建議，只做輿情狀態描述。
3. 若同一事件在多個標題重複出現，指出這是「集中討論的焦點」；若標題彼此
   矛盾（例如同時有利多與利空标题），要點出來，不要選擇性只講一邊。
4. 若資料量很少（標題不到 5 則），要說明「樣本數少，僅供參考」。

輸出格式（**臺灣用語的繁體中文，不可出現任何簡體字**，200 字以內）：
**焦點**：這幾天在討論什麼（1-2 句）
**輿情傾向**：偏多/偏空/中性，及依據
**留意**：條列 0-2 點需要留意的矛盾或風險（沒有就省略這段）"""


def _titles_block(label: str, items: list[dict], limit: int = 12) -> str:
    rows = []
    for it in (items or [])[:limit]:
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        date = it.get("date") or it.get("published") or ""
        rows.append(f"- {title}" + (f"（{date}）" if date else ""))
    if not rows:
        return ""
    return f"【{label}】\n" + "\n".join(rows)


def build_news_prompt(symbol: str, buzz: dict) -> str:
    """把 analyze_social_buzz() 已經抓到的標題清單組成 prompt。"""
    lines = [f"股票代碼：{symbol}"]
    if buzz.get("stock_name"):
        lines.append(f"名稱：{buzz['stock_name']}")
    lines.append(
        f"熱度分數 {buzz.get('buzz_score', '無資料')}（{buzz.get('buzz_level', '')}），"
        f"情緒傾向 {buzz.get('sentiment_label', '無資料')}"
    )

    ptt = buzz.get("ptt") or {}
    if ptt.get("post_count"):
        lines.append(f"PTT 討論 {ptt['post_count']} 篇，看多 {ptt.get('bullish_count', 0)}／看空 {ptt.get('bearish_count', 0)}")
        block = _titles_block("PTT 標題", ptt.get("posts") or [])
        if block:
            lines.append(block)

    news = buzz.get("news") or {}
    block = _titles_block("一般新聞標題", news.get("articles") or [])
    if block:
        lines.append(block)

    finance_news = buzz.get("finance_news") or {}
    block = _titles_block("財經媒體標題", finance_news.get("articles") or [])
    if block:
        lines.append(block)

    fact_check = buzz.get("fact_check") or {}
    block = _titles_block("事實查核", fact_check.get("items") or [])
    if block:
        lines.append(block)

    return "\n\n".join(lines)


async def build_news_ai_summary(symbol: str, buzz: dict) -> dict:
    """LLM 摘要目前的輿情狀態。快取比照 social_buzz 的日頻節奏，6 小時。"""
    from datetime import date

    from ..db.cache import get_cache, set_cache
    from ..llm import llm_complete

    cache_key = f"news_ai_summary:v1:{symbol}:{date.today().isoformat()}"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return {**cached, "cached": True}
    except Exception:
        pass

    prompt = build_news_prompt(symbol, buzz)
    text = await llm_complete(SYSTEM_PROMPT, prompt, max_tokens=1200, temperature=0.3)

    result = {"symbol": symbol, "summary": text, "as_of": date.today().isoformat(), "cached": False}
    try:
        await set_cache(cache_key, result, "ai_summary")
    except Exception:
        pass
    return result
