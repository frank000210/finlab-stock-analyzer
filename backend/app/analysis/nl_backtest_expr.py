"""白話回測條件生成（BB4）。

跟 W8 自然語言選股同一個設計原則：LLM 只負責把白話描述轉成「結構化」輸出
（這裡是買賣條件運算式字串），不負責執行——實際判斷買賣點是
`expr_lang.py` 的固定 parser/evaluator 在跑，LLM 生不出語法規則以外的東西。
回傳前一定會先用 parser 驗證過，parse 不過就重試一次（把錯誤訊息餵回去讓
LLM 自己修正），還是不過就誠實回報失敗，不會把破損的運算式交給前端。
"""

from __future__ import annotations

import json
import logging
import re

from ..backtest.expr_lang import ALL_INDICATORS, ExpressionError, parse_condition

logger = logging.getLogger(__name__)

_INDICATOR_LIST = ", ".join(sorted(ALL_INDICATORS))

SYSTEM_PROMPT = f"""你是台股技術面回測條件產生助理。使用者會用白話描述進出場想法，你要把它轉成
本系統定義的「條件運算式」，不做任何判斷或建議——條件是否成立由系統的固定
公式計算，你只負責把白話翻譯成語法正確的運算式。

可用指標（大寫、不可使用清單以外的名稱）：{_INDICATOR_LIST}
- MA/EMA/RSI/ATR/VOLUME_RATIO 需要一個週期參數，例如 RSI(14)、MA(20)。
- 其餘指標不需要參數，直接寫指標名稱，不要加括號（例如 CLOSE、MACD_HIST、BB_UPPER、ADX）。
- VOLUME_RATIO(n) 代表「今日成交量 ÷ n 日均量」。

可用運算子：
- 比較：> < >= <= == !=
- 交叉：CROSSES_ABOVE（由下往上穿越）、CROSSES_BELOW（由上往下穿越）
- 邏輯：AND、OR、NOT，可用括號分組

規則：
1. 只輸出 JSON，不要其他文字、不要加 markdown code fence。
2. 欄位：{{"buy_expr": "買進條件運算式", "sell_expr": "賣出條件運算式", "description": "20字以內覆述你的理解"}}
3. buy_expr / sell_expr 一定要是完整的比較式（例如 RSI(14) < 30），不能只寫一個指標名稱、也不能省略比較符號。
4. 使用者若沒提到賣出/出場條件，用該指標常見的相反方向門檻補一個合理的賣出條件（例如買進用 RSI < 30，賣出可以用 RSI > 70），並在 description 裡註明是系統補的。
5. 使用者描述裡明確提到的指標名稱（例如「布林通道」「MACD」「KD」）務必對應到
   該指標本身的運算式（BB_UPPER/BB_LOWER、MACD_DIF/MACD_DEA/MACD_HIST、
   KD_K/KD_D），不要因為不確定就默默改用 MA 或 CLOSE 之類更簡單的指標替代。
6. 範例：
   使用者：「RSI 低於 30 而且成交量爆量兩倍以上就買，RSI 高於 70 就賣」
   輸出：{{"buy_expr": "RSI(14) < 30 AND VOLUME_RATIO(20) > 2", "sell_expr": "RSI(14) > 70", "description": "RSI超賣+爆量買進，RSI超買賣出"}}

   使用者：「收盤價跌破布林通道下軌就賣出，站回下軌之上就買進」
   輸出：{{"buy_expr": "CLOSE CROSSES_ABOVE BB_LOWER", "sell_expr": "CLOSE CROSSES_BELOW BB_LOWER", "description": "站回布林下軌買進，跌破下軌賣出"}}
"""

_RETRY_PROMPT_TMPL = """你上一次的輸出無法通過語法檢查，錯誤如下，請只根據錯誤修正後重新輸出完整
的 JSON（一樣的格式，不要加其他文字）：

上次輸出：
{prev_output}

錯誤訊息：
{error}
"""


class ExpressionGenerationError(RuntimeError):
    """AI 生成的條件即使重試後仍無法通過語法檢查。"""


def _extract_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _validate(parsed: dict) -> tuple[str, str, str] | None:
    """回傳 (buy_expr, sell_expr, description) 或 None（語法/欄位不合法）。"""
    buy_expr = str(parsed.get("buy_expr", "")).strip()
    sell_expr = str(parsed.get("sell_expr", "")).strip()
    description = str(parsed.get("description", "")).strip()[:60]
    if not buy_expr or not sell_expr:
        return None
    parse_condition(buy_expr)  # 丟 ExpressionError 就整個失敗，讓上層決定要不要重試
    parse_condition(sell_expr)
    return buy_expr, sell_expr, description


async def generate_expression(query: str) -> dict:
    from ..llm import llm_complete

    query = (query or "").strip()
    if not query:
        raise ExpressionGenerationError("請輸入你的進出場想法。")

    raw = await llm_complete(SYSTEM_PROMPT, query, max_tokens=500, temperature=0.2)
    parsed = _extract_json(raw)
    try:
        result = _validate(parsed)
    except ExpressionError as exc:
        result = None
        last_error = str(exc)
    else:
        last_error = "" if result else "JSON 格式不對或缺少 buy_expr/sell_expr 欄位。"

    if result is None:
        # 重試一次：把上次輸出跟錯誤訊息餵回去，讓 LLM 自己修正。
        logger.info("expression generation retry after validation failure: %s", last_error)
        retry_user = _RETRY_PROMPT_TMPL.format(prev_output=raw[:500], error=last_error)
        raw2 = await llm_complete(SYSTEM_PROMPT, retry_user, max_tokens=500, temperature=0.1)
        parsed2 = _extract_json(raw2)
        try:
            result = _validate(parsed2)
        except ExpressionError as exc:
            raise ExpressionGenerationError(f"AI 生成的條件語法不正確，請換個描述方式再試一次（{exc}）") from exc
        if result is None:
            raise ExpressionGenerationError("AI 沒有生成有效的買賣條件，請換個描述方式再試一次。")

    buy_expr, sell_expr, description = result
    return {"buy_expr": buy_expr, "sell_expr": sell_expr, "description": description}
