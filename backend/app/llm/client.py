"""LLM 客戶端抽象層（W0）。

供應商中立：走 OpenAI 相容的 /chat/completions，換服務只要改 settings 的
llm_base_url / llm_model，其他程式碼不用動。目前接 OpenCode Go。

實測（2026-07，5 個模型）得到的三個關鍵設計約束：
1. **必須帶 User-Agent**——OpenCode 前面有 Cloudflare，預設的 Python UA 會
   被判定為 bot 直接回 403（error code 1010）。
2. **必須處理「空內容」**——部分模型（deepseek-v4-flash / glm-5.1）會把全部
   輸出放進 reasoning token，content 回空字串。這不是錯誤回應、HTTP 仍是
   200，所以要主動偵測並改用備援模型重試。
3. **延遲 15~40 秒**——呼叫端一律要「使用者主動觸發 + 快取」，絕不可放在
   頁面首屏的必要路徑上。

失效原則：LLM 不可用時一律拋 LLMUnavailable，呼叫端負責降級顯示；絕不能
讓 LLM 故障影響網站既有功能。
"""

from __future__ import annotations

import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# Cloudflare bot 檢查：一定要有可辨識的 User-Agent
_USER_AGENT = "finlab-stock-analyzer/1.0 (+https://finlab-app.zeabur.app)"


class LLMUnavailable(RuntimeError):
    """LLM 不可用（未設定 key／額度用盡／上游錯誤／回空內容）。"""


def is_llm_configured() -> bool:
    from ..config.settings import get_settings

    return bool(get_settings().opencode_api_key)


async def _check_and_bump_daily_quota() -> None:
    """每日呼叫上限：避免程式異常或濫用把訂閱額度燒光。

    計數存 Mongo settings（key 含日期，天然每日重置）。Mongo 不可用時
    「放行」而不是擋下——沒有計數能力不該讓功能整個不能用。
    """
    from ..config.settings import get_settings
    from ..db.cache import get_setting, set_setting

    limit = get_settings().llm_daily_call_limit
    key = f"llm_calls:{date.today().isoformat()}"
    try:
        used = int(await get_setting(key, 0) or 0)
    except Exception:
        return
    if used >= limit:
        raise LLMUnavailable(f"今日 AI 呼叫次數已達上限（{limit} 次），請明日再試。")
    try:
        await set_setting(key, used + 1)
    except Exception:
        pass


async def _post_once(model: str, system: str, user: str,
                     max_tokens: int, temperature: float) -> str:
    from ..config.settings import get_settings

    s = get_settings()
    url = f"{s.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    async with httpx.AsyncClient(timeout=s.llm_timeout_seconds) as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {s.opencode_api_key}",
                "Content-Type": "application/json",
                "User-Agent": _USER_AGENT,
            },
            json=payload,
        )
    if resp.status_code != 200:
        # 不把上游回應原文外洩給前端（可能含 key/內部路徑），只留狀態碼。
        logger.warning("LLM upstream %s: %s", resp.status_code, resp.text[:300])
        raise LLMUnavailable(f"AI 服務暫時無法使用（上游狀態 {resp.status_code}）")

    data = resp.json()
    choices = data.get("choices") or []
    content = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    if not content:
        # 見模組說明第 2 點：HTTP 200 但內容為空，屬模型行為而非傳輸錯誤。
        raise LLMUnavailable("AI 回應內容為空")
    return content


async def llm_complete(system: str, user: str, *, max_tokens: int = 800,
                       temperature: float = 0.3) -> str:
    """呼叫 LLM 並回傳純文字。失敗一律拋 LLMUnavailable，由呼叫端降級。

    主模型回空內容或失敗時，自動改用備援模型再試一次（實測有模型會把輸出
    全部放進 reasoning token 而回空字串，換模型即可解決）。
    """
    from ..config.settings import get_settings

    s = get_settings()
    if not s.opencode_api_key:
        raise LLMUnavailable("尚未設定 AI 服務金鑰（OPENCODE_API_KEY）")

    await _check_and_bump_daily_quota()

    try:
        return await _post_once(s.llm_model, system, user, max_tokens, temperature)
    except LLMUnavailable as first_err:
        fallback = s.llm_fallback_model
        if not fallback or fallback == s.llm_model:
            raise
        logger.warning("LLM primary model %s failed (%s), trying fallback %s",
                       s.llm_model, first_err, fallback)
        try:
            return await _post_once(fallback, system, user, max_tokens, temperature)
        except LLMUnavailable:
            raise first_err
    except httpx.TimeoutException as exc:
        raise LLMUnavailable("AI 服務回應逾時") from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed: %s", exc)
        raise LLMUnavailable("AI 服務暫時無法使用") from exc
