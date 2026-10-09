"""大戶（主力）估計成本——AI 白話公式說明 + 逐步試算 + 5 日情境教學。

跟 W2 個股 AI 摘要（analysis/ai_summary.py）同一套防幻覺原則：
所有數字都由 chip_cost.compute_major_cost() 算好後放進 prompt，LLM 只負責
把公式與試算過程講成人話，不得自行編造或預測任何未提供的數字。「5 日可能
情境」這段刻意要求 LLM 講清楚是教育性質的情境說明、不是預測，避免投資新手
誤把 AI 輸出當成報明牌。

時事落地（v3）：llm_complete() 是無狀態單次呼叫（見 llm/client.py），沒有
工具呼叫/上網搜尋能力，LLM 對「最近消息面」的認知永遠停在訓練資料截止日、
可能與現況不符。與其接一個全新的即時搜尋工具鏈（牽動供應商中立的
OpenAI-相容 /chat/completions 架構），改用網站既有的新聞爬蟲基礎設施
（social_buzz.py，W4/J 系列已有的 PTT/Google News/財經媒體來源，本來就有
真實日期）先抓這檔股票最近的真實新聞標題，餵進 prompt 當作「時空背景」，
並在系統提示詞明文禁止在這之外對「近期消息面」做任何具體陳述。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是台股籌碼分析教學助理，服務對象是完全沒有背景知識的投資新手。
使用者想了解「大戶（主力）估計成本」這項指標。

嚴格規則（違反即為錯誤輸出）：
1. 只能使用使用者訊息中提供的數字與新聞標題，絕對禁止引用、推算或編造任何
   未提供的資料或數字。
2. 不得給投資建議：不說買進/賣出/加碼/減碼/該進場/該停損，也不得給目標價。
3. 用詞盡量白話、對新手友善；出現「法人」「乖離率」「籌碼集中度」等術語時，
   要順手用一句話解釋是什麼意思。
4. 第三部分「5 日可能情境」必須明確定位成教育性質的情境說明，不是預測——
   要清楚提醒籌碼面只是影響股價的其中一個因素，實際走勢可能因消息面、大盤
   等各種原因而不同，不構成投資建議，也不用給時間精確到「第幾天」的預測。
5. 【重要】你對「近期消息面」「市場現況」「最新發展」完全沒有即時資訊——
   你的訓練資料有截止日，之後發生的事你並不知道。除非使用者訊息裡的
   「近期相關新聞標題」區塊有列出具體新聞，否則絕對不能對這檔股票的近期
   消息面、公司動態、產業現況做出任何具體陳述（例如不能說「近期市場對該
   公司財報看法正面」「最近有利多消息」這類話）；如果新聞列表是空的，就
   明講「目前查無這檔股票的近期新聞可供參考」，不要編造或憑訓練資料猜測。
   即使新聞列表有提供新聞，也只能引用列表裡實際出現的標題與日期，不能
   延伸推論成沒有寫出的具體事實。

輸出格式（臺灣用語的繁體中文，不可出現簡體字，總長 500 字以內）：
**① 大戶成本怎麼算**：白話解釋公式的邏輯（不用寫數學符號，用講的）
**② 這檔股票的實際試算過程**：用使用者提供的真實數字，一步一步代入，展示
   怎麼算出最後的成本值（可以只挑幾天當範例，不用把每一天都列出來）
**③ 股價之後可能的情境（僅供參考，非預測）**：根據目前的成本乖離與籌碼
   集中度，用新手聽得懂的話列出 2-3 種市場上常見的解讀情境（例如：現價貼近
   成本、遠高於成本、遠低於成本，分別代表什麼、又各自有哪些常見的後續可能），
   若「近期相關新聞標題」有提供實際新聞，可以簡短提及作為背景參考（僅限
   引用標題本身，不可延伸推論未寫出的細節），結尾務必重申這只是教育性質的
   情境說明，不是預測也不是投資建議"""


async def _fetch_recent_news(symbol: str) -> list[dict]:
    """抓這檔股票最近的真實新聞標題（含日期），當作 AI 的時空背景。

    只需要標題/日期/來源，不需要 analyze_social_buzz() 的完整分析（PTT 情緒、
    集保、當沖等），刻意繞開那支函式改直接呼叫底層的新聞抓取，省去不相關
    來源（PTT/事實查核/成交量）的延遲與外部呼叫。任一來源失敗都不讓整個
    AI 說明功能跟著失敗——查無新聞時系統提示詞會要求 LLM 誠實講「查無新聞」，
    而不是逼呼叫端整個報錯。
    """
    from .social_buzz import _scrape_finance_news, _scrape_news

    search_terms = [symbol]
    results = await asyncio.gather(
        _scrape_news(search_terms), _scrape_finance_news(search_terms),
        return_exceptions=True,
    )
    articles: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("_fetch_recent_news: source failed for %s: %s", symbol, r)
            continue
        articles.extend(r.get("articles") or [])

    seen: set[str] = set()
    unique = []
    for a in articles:
        title = a.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique.append(a)
    return unique[:6]

_ADVICE_PATTERNS = ("建議買進", "建議賣出", "建議加碼", "建議減碼", "可以買進", "應該買進", "應該賣出", "目標價")


def _fmt(v, unit: str = "") -> str:
    if v is None:
        return "無資料"
    if isinstance(v, (int, float)):
        return f"{v}{unit}"
    return f"{v}{unit}"


def _build_user_prompt(symbol: str, cost: dict, news: list[dict] | None = None) -> str:
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

    # 時事落地（v3）：給 LLM 一個明確的「現在時空」錨點，避免它憑訓練資料
    # 對近期消息面做出可能過時或錯誤的具體陳述——規則 5 要求它只能引用這裡
    # 實際列出的標題。
    lines.append("")
    lines.append("近期相關新聞標題（僅供時空背景參考，非籌碼數據本身；只能引用下列實際標題，不可自行延伸或用你自己的訓練資料補充）：")
    if news:
        for n in news:
            lines.append(f"　[{n.get('published') or '日期不明'}] {n.get('title', '')}（來源：{n.get('source', '')}）")
    else:
        lines.append("　（查無這檔股票的近期新聞，請在說明中誠實告知使用者你目前沒有近期消息面資訊）")
    return "\n".join(lines)


async def explain_major_cost(symbol: str, days: int = 90) -> dict:
    """組裝大戶成本的既有計算結果 → 呼叫 LLM 說明 → 回傳。快取一天。"""
    from datetime import date

    from ..api.chip import _build_chip_analysis
    from ..db.cache import get_cache, set_cache
    from ..llm import llm_complete

    # v3：user prompt 新增「近期相關新聞標題」區塊（時事落地，見本檔案開頭
    # 說明），版號再升級一次，理由同 v1→v2：內容形狀變了，避免舊版快取殘留
    # 造成前端顯示跟系統提示詞規則對不上（提示詞規則 5 提到的新聞區塊，舊
    # 快取裡的 explanation 卻是在沒看過任何新聞的情況下產生的）。
    cache_key = f"major_cost_ai:v3:{symbol}:{days}:{date.today().isoformat()}"
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

    try:
        news = await _fetch_recent_news(symbol)
    except Exception:
        logger.exception("_fetch_recent_news failed for %s", symbol)
        news = []

    user_prompt = _build_user_prompt(symbol, cost, news)
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
        "prompt": {"system": SYSTEM_PROMPT, "user": user_prompt},
        "cached": False,
    }
    try:
        await set_cache(cache_key, out, "ai_summary")
    except Exception:
        pass
    return out
