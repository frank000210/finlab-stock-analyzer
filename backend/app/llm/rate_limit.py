"""LLM 端點 per-IP 速率限制（X1）。

網站本身沒有使用者登入（除了 admin），每個 LLM 端點都能被任何人匿名連點。
既有的 `llm_daily_call_limit`（見 client.py）只擋「全站今天總共打了幾次」，
沒有辦法分辨是很多不同使用者各打一兩次，還是單一來源在狂點——後者會讓
全站共用的每日額度瞬間被單一來源耗盡，其他人跟著遭殃。這裡加一層獨立
的 per-IP 節流，用 FastAPI Depends 掛在各端點上，兩層各司其職。

用既有的 Mongo TTL 快取（db/cache.py）實作滑動窗口的簡化版：每次呼叫把
過期時間往後推 IP_WINDOW_MINUTES 分鐘，計數到門檻就擋。取不到來源 IP 或
Mongo 不可用時一律放行——節流機制本身故障不該讓功能整個打不開。
"""

from __future__ import annotations

from fastapi import HTTPException, Request

IP_WINDOW_MINUTES = 10
IP_MAX_CALLS = 6  # 10 分鐘內同一 IP 最多 6 次，容得下正常重試/換頁使用，擋得住狂點


async def check_llm_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else None
    if not ip:
        return

    from ..db.cache import get_cache, set_cache

    key = f"llm_rate:{ip}"
    try:
        count = await get_cache(key)
    except Exception:
        return
    count = int(count or 0)
    if count >= IP_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"AI 功能呼叫過於頻繁，請 {IP_WINDOW_MINUTES} 分鐘後再試。",
        )
    try:
        await set_cache(key, count + 1, "rate_limit")
    except Exception:
        pass
