"""大戶（主力）估計成本——AI 白話公式說明 + 逐步試算 + 5 日情境教學。

跟 W2 個股 AI 摘要（analysis/ai_summary.py）同一套防幻覺原則：
所有數字都由 chip_cost.compute_major_cost() 算好後放進 prompt，LLM 只負責
把公式與試算過程講成人話，不得自行編造或預測任何未提供的數字。「5 日可能
情境」這段刻意要求 LLM 講清楚是教育性質的情境說明、不是預測，避免投資新手
誤把 AI 輸出當成報明牌。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是台股籌碼分析教學助理，服務對象是完全沒有背景知識的投資新手。
使用者想了解「大戶（主力）估計成本」這項指標。

嚴格規則（違反即為錯誤輸出）：
1. 只能使用使用者訊息中提供的數字，絕對禁止引用、推算或編造任何未提供的資料。
2. 不得給投資建議：不說買進/賣出/加碼/減碼/該進場/該停損，也不得給目標價。
3. 用詞盡量白話、對新手友善；出現「法人」「乖離率」「籌碼集中度」等術語時，
   要順手用一句話解釋是什麼意思。
4. 第三部分「5 日可能情境」必須明確定位成教育性質的情境說明，不是預測——
   要清楚提醒籌碼面只是影響股價的其中一個因素，實際走勢可能因消息面、大盤
   等各種原因而不同，不構成投資建議，也不用給時間精確到「第幾天」的預測。

輸出格式（臺灣用語的繁體中文，不可出現簡體字，總長 500 字以內）：
**① 大戶成本怎麼算**：白話解釋公式的邏輯（不用寫數學符號，用講的）
**② 這檔股票的實際試算過程**：用使用者提供的真實數字，一步一步代入，展示
   怎麼算出最後的成本值（可以只挑幾天當範例，不用把每一天都列出來）
**③ 股價之後可能的情境（僅供參考，非預測）**：根據目前的成本乖離與籌碼
   集中度，用新手聽得懂的話列出 2-3 種市場上常見的解讀情境（例如：現價貼近
   成本、遠高於成本、遠低於成本，分別代表什麼、又各自有哪些常見的後續可能），
   結尾務必重申這只是教育性質的情境說明，不是預測也不是投資建議"""

_ADVICE_PATTERNS = ("建議買進", "建議賣出", "建議加碼", "建議減碼", "可以買進", "應該買進", "應該賣出", "目標價")


def _fmt(v, unit: str = "") -> str:
    if v is None:
        return "無資料"
    if isinstance(v, (int, float)):
        return f"{v}{unit}"
    return f"{v}{unit}"


def _build_user_prompt(symbol: str, cost: dict) -> str:
    lines = [f"股票代碼：{symbol}"]
    lines.append(f"分析區間：近 {cost.get('days_analyzed')} 個交易日，其中法人買超天數 {cost.get('buy_days_count')} 天")

    sample = cost.get("buy_days_sample") or []
    if sample:
        lines.append("最近幾個法人買超日明細（日期／當日收盤價／法人買超股數）：")
        for d in sample:
            lines.append(f"　{d['date']}：收盤 {d['close']} 元，法人買超 {d['net']:,} 股")

    # buy_shares/buy_cost 舊版快取（chip_analysis cache 尚未過期時）可能沒有這
    # 兩個欄位，用 or 0 防呆，不要讓千分位格式化直接對 None 炸掉。
    lines.append(f"買超股數合計：{(cost.get('buy_shares') or 0):,} 股")
    lines.append(f"買超金額合計（各買超日「收盤價 × 當日買超股數」加總）：約 {(cost.get('buy_cost') or 0):,.0f} 元")
    lines.append(f"大戶估計成本 = 買超金額合計 ÷ 買超股數合計 = {_fmt(cost.get('cost'), ' 元')}")
    lines.append(f"目前股價：{_fmt(cost.get('last_close'), ' 元')}")
    lines.append(f"乖離率（現價相對估計成本高出或低於幾 %）：{_fmt(cost.get('deviation'), '%')}")
    lines.append(f"系統判讀：{cost.get('cost_verdict')}——{cost.get('cost_description')}")
    lines.append(f"籌碼集中度（區間法人累積淨買超佔總成交量比重）：{_fmt(cost.get('concentration'), '%')}")
    lines.append(f"集中度判讀：{cost.get('conc_verdict')}——{cost.get('conc_description')}")
    return "\n".join(lines)


async def explain_major_cost(symbol: str, days: int = 90) -> dict:
    """組裝大戶成本的既有計算結果 → 呼叫 LLM 說明 → 回傳。快取一天。"""
    from datetime import date

    from ..api.chip import _build_chip_analysis
    from ..db.cache import get_cache, set_cache
    from ..llm import llm_complete

    cache_key = f"major_cost_ai:v1:{symbol}:{days}:{date.today().isoformat()}"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return {**cached, "cached": True}
    except Exception:
        pass

    result = await _build_chip_analysis(symbol, days)
    cost = result.get("major_cost")
    if not cost or cost.get("cost") is None:
        raise ValueError("近期法人買賣超資料不足，無法估算大戶成本，AI 無法據此說明。")

    user_prompt = _build_user_prompt(symbol, cost)
    text = await llm_complete(SYSTEM_PROMPT, user_prompt, max_tokens=1800, temperature=0.3)

    if any(p in text for p in _ADVICE_PATTERNS):
        logger.warning("major_cost_ai explanation for %s contained advice-like wording", symbol)
        text += "\n\n（系統提醒：以上僅為籌碼數據的教育性說明，非投資建議，請自行查證並審慎判斷。）"

    dist = result.get("distribution") or {}
    out = {
        "symbol": symbol,
        "explanation": text,
        "as_of": dist.get("data_date") or date.today().isoformat(),
        "model_note": "由 AI 依網站已計算好的大戶成本數據生成說明；所有數字均來自網站計算結果，AI 僅負責解讀與教學，不構成投資建議。",
        "cached": False,
    }
    try:
        await set_cache(cache_key, out, "ai_summary")
    except Exception:
        pass
    return out
