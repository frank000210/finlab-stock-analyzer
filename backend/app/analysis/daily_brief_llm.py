"""盤後日報自然語言化（W9）。

盤後日報走排程（每個交易日固定時間透過 Telegram 推播），不是使用者主動
點擊觸發——這點跟 W2/W4/W6 等「使用者按按鈕才呼叫 LLM」的功能不同，必須
更嚴格地保證失敗不影響推播：LLM 只負責把「已經算好的結構化資料」重寫成
更順的白話文，呼叫端一律要有沒有 LLM 版本也能正常運作的 fallback。

設計：LLM 產生的是「導讀」，加在結構化模板前面而非取代它——結構化模板
本身已含代碼/日期/警示等具體數字與固定的免責聲明，這些不能交給 LLM 自由
改寫（自由發揮時可能省略或改寫掉某個代碼，對實際交易決策是不可接受的
損失）。所以這裡的 prompt 只要求一段簡短導讀，不要求 LLM 自己重複寫免責
聲明或列出所有明細，由呼叫端（api/risk.py）保證這些一定存在。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是台股盤後日報播報員。使用者會給你今天的市場體制、觀察清單中
表現最好的幾檔設定、以及需要注意的警示標籤（結構化資料）。你的輸出會被放在
一份已含完整明細的正式日報「前面」當作導讀，讀者接下來一定會看到完整明細，
所以你不需要也不應該重複列出所有代碼/數字明細。

規則：
1. 只能使用提供的資料做總結性描述，不得新增任何未提供的數字或判斷。
2. 不得提供投資建議。
3. 語氣像簡短的播報稿開場白，2-3 句話點出今天的整體氛圍即可，不要條列。
4. 100 字以內，繁體中文，不可有簡體字，不要加免責聲明（後面的完整日報
   已經有）。"""


async def rewrite_brief_prose(as_of: str, regime_data: dict | None, top: list[dict], warn_lines: list[str]) -> str | None:
    """成功回傳改寫後全文；任何失敗（含逾時、未設定、額度用盡）一律回傳
    None，呼叫端要用原本的模板文字當 fallback，不可讓排程推播中斷。"""
    from ..llm import LLMUnavailable, is_llm_configured, llm_complete

    if not is_llm_configured():
        return None

    lines = [f"日期：{as_of}"]
    if regime_data:
        lines.append(
            f"市場體制：{regime_data.get('label')}（風險係數 ×{regime_data.get('risk_mult')}，"
            f"0050 {regime_data.get('close')} vs 年線 {regime_data.get('ma200')}）"
        )
    if top:
        lines.append("今日最佳設定：" + "；".join(
            f"{t['symbol']}{t.get('name', '')} {t['setup_total']}分 {t.get('trend', '')} {t['chg_pct']:+}%"
            for t in top
        ))
    if warn_lines:
        lines.append("注意事項：" + "；".join(warn_lines[:8]))

    try:
        text = await llm_complete(SYSTEM_PROMPT, "\n".join(lines), max_tokens=600, temperature=0.4)
        return text.strip()
    except LLMUnavailable as exc:
        logger.info("daily brief LLM rewrite unavailable, falling back to template: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily brief LLM rewrite failed, falling back to template: %s", exc)
        return None
