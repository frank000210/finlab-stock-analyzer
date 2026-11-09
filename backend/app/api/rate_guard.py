"""共用的固定視窗限流（每個 IP、每 10 分鐘），只計「真的要打 FinMind」的請求。

FinMind 免費額度約 600 次／小時，整個網站共用；快取命中的請求不碰 FinMind，
所以只有未命中時才依預估呼叫數扣額度（見 api/etf_compare.py 的同型作法與
project_etf_compare_ratelimit_design：固定視窗，滑動視窗會讓「被擋越按越久」）。
計數機制本身故障時放行，不擋功能。
"""

from __future__ import annotations

from fastapi import HTTPException, Request


def too_many(seconds_left: int) -> HTTPException:
    minutes = max(1, -(-seconds_left // 60))
    return HTTPException(
        status_code=429,
        detail=f"查詢過於頻繁，請約 {minutes} 分鐘後再試。",
        headers={"Retry-After": str(max(seconds_left, 1))},
    )


async def consume(request: Request, kind: str, cost: int, limit: int) -> None:
    """固定視窗計數；超量回 429（附剩餘秒數）。"""
    from ..api.analytics import _get_client_ip
    from ..db.cache import consume_fixed_window

    ip = _get_client_ip(request)
    if not ip or ip == "unknown":
        return
    try:
        count, left = await consume_fixed_window(f"{kind}:{ip}", cost)
    except Exception:
        return
    if count > limit:
        raise too_many(left)
