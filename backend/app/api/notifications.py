"""Notification API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..notify import LineNotifier

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class LineTestRequest(BaseModel):
    """LINE 測試通知請求。token 走 request body,避免出現在 URL/存取日誌。"""

    token: Optional[str] = None


@router.post("/line/test")
async def test_line_notification(payload: Optional[LineTestRequest] = None):
    """Test LINE notification.(token 由 body 傳入,不走 query string)"""
    notifier = LineNotifier(token=payload.token if payload else None)
    success = await notifier.test_connection()
    if not success:
        raise HTTPException(status_code=400, detail="LINE notification failed. Check token.")
    return {"success": True, "data": {"message": "Test notification sent successfully"}}
