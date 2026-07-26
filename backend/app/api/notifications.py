"""Notification API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..notify import LineNotifier

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# LL3：這支端點接受呼叫端自己傳入任意 token 並回報有效與否，等於是一個公開
# 無驗證的「LINE Notify token 有效性 oracle」——沒有節流的話，可以拿來批次
# 驗證大量竊取/猜測來的 token。合法用途（設定頁「測試」按鈕）本身就需要
# 接受任意 token，所以不能直接擋掉，改用跟其他公開端點一致的頻率限制。
_LINE_TEST_WINDOW_MINUTES = 10
_LINE_TEST_MAX_CALLS = 10


async def _check_line_test_rate_limit(request: Request) -> None:
    from ..api.analytics import _get_client_ip
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    try:
        count = await increment_rate_limit(f"line_test_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _LINE_TEST_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"測試請求過於頻繁，請 {_LINE_TEST_WINDOW_MINUTES} 分鐘後再試。",
        )


class LineTestRequest(BaseModel):
    """LINE 測試通知請求。token 走 request body,避免出現在 URL/存取日誌。"""

    token: Optional[str] = None


@router.post("/line/test", dependencies=[Depends(_check_line_test_rate_limit)])
async def test_line_notification(payload: Optional[LineTestRequest] = None):
    """Test LINE notification.(token 由 body 傳入,不走 query string)"""
    notifier = LineNotifier(token=payload.token if payload else None)
    success = await notifier.test_connection()
    if not success:
        raise HTTPException(status_code=400, detail="LINE notification failed. Check token.")
    return {"success": True, "data": {"message": "Test notification sent successfully"}}
