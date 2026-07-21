"""交易日誌 AI 複盤教練（W6）＋進場理由品質檢查（W7）。

設計約束（來自研究既有 E15 複盤教練時發現）：交易日誌全部存在瀏覽器
localStorage，後端沒有交易紀錄的資料庫——這裡的 LLM 端點吃的是前端主動
送來的一批交易資料，不是後端自己查出來的，跟 W2/W4 那種「後端已有資料
直接組 prompt」的模式不同。

跟既有規則式教練（JournalView.vue 的 coachInsights）分工：規則式抓的是
「賺賠不對稱」「過度交易」「停損沒執行」這類寫死能算出來的統計模式；
AI 複盤負責找規則沒設計到的、更細緻的敘事型模式（例如某個 catalyst 類型
的勝率特別差、連續虧損後的下一筆表現）。兩者並存，不是取代關係。
"""

from __future__ import annotations

MAX_TRADES_IN_PROMPT = 30

COACH_SYSTEM_PROMPT = """你是交易紀律複盤教練。使用者會給你一批已平倉的交易紀錄
（含代碼/方向/進出場價/損益 R 值/型態標籤/進場理由）與整體統計數據。

規則：
1. 只能根據使用者提供的交易紀錄與統計數據做分析，不得杜撰任何未列出的交易。
2. 不得提供具體投資建議（不說該買哪檔、該設多少停損），只做「行為模式」分析：
   找出重複出現、值得注意的交易行為特徵。
3. 你的分析要跟「賺賠不對稱」「過度交易」「停損沒執行」這類基本統計問題區分
   開——假設使用者已經知道這些基本面，你要找的是更細緻的模式，例如：
   特定進場理由類型的勝率差異、連續虧損後下一筆的表現、特定商品/方向的
   表現差異、部位大小與結果的關聯。若看不出有意義的模式，誠實說
   「目前樣本沒有看出明顯的細緻模式」，不要硬湊。
4. 若樣本數少於 15 筆，要提醒「樣本數少，模式可能只是巧合」。

輸出格式（**臺灣用語的繁體中文，不可出現任何簡體字**，300 字以內，條列 2-4 點）"""

CATALYST_SYSTEM_PROMPT = """你是交易紀律教練，專門檢查「進場理由」寫得夠不夠具體。

規則：
1. 只根據使用者提供的這一句進場理由文字判斷，不對交易本身的對錯發表意見。
2. 判斷標準：是否具體可驗證（例如「Q3財報營收超預期20%」）vs. 空泛主觀
   （例如「感覺會漲」「線型很漂亮」）。技術面理由（如「站上季線」）若有明確
   條件也算具體。
3. 不得給出投資建議。

輸出格式：一句話（30字以內，繁體中文，不可有簡體字），先給評價（具體/普通/空泛），
再給一句改進建議（若已經很具體則說「已足夠具體」）。只輸出這一句話。"""


def _build_coach_prompt(trades: list[dict], stats: dict) -> str:
    lines = [
        f"整體統計：{stats.get('count', 0)} 筆已平倉、勝率 {round((stats.get('winRate') or 0) * 100, 1)}%、"
        f"期望值 {round(stats.get('expectancyR') or 0, 2)}R、盈虧比 {round(stats.get('profitFactor') or 0, 2)}",
        "",
        "近期交易明細：",
    ]
    for t in trades[-MAX_TRADES_IN_PROMPT:]:
        parts = [
            t.get("symbol", ""),
            t.get("side", ""),
            f"進{t.get('entry')}",
            f"出{t.get('exit')}" if t.get("exit") is not None else "",
            f"R={t.get('r_multiple')}" if t.get("r_multiple") is not None else "",
            f"型態:{t.get('tag')}" if t.get("tag") else "",
            f"理由:{t.get('catalyst')}" if t.get("catalyst") else "",
        ]
        lines.append("- " + " ".join(p for p in parts if p))
    return "\n".join(lines)


async def build_ai_coach(trades: list[dict], stats: dict) -> dict:
    from ..llm import llm_complete

    prompt = _build_coach_prompt(trades, stats)
    text = await llm_complete(COACH_SYSTEM_PROMPT, prompt, max_tokens=1200, temperature=0.4)
    return {"insight": text}


async def check_catalyst_quality(symbol: str, side: str, catalyst: str) -> dict:
    from ..llm import llm_complete

    prompt = f"股票：{symbol}（{side}）\n進場理由：{catalyst}"
    text = await llm_complete(CATALYST_SYSTEM_PROMPT, prompt, max_tokens=300, temperature=0.2)
    return {"assessment": text.strip()}
