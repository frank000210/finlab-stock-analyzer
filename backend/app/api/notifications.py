"""Notification API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..notify import LineNotifier

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationSettings(BaseModel):
    line_token: Optional[str] = None
    price_alert: bool = True
    technical_signal: bool = True
    ai_prediction: bool = True
    ai_confidence_threshold: float = 0.7


@router.post("/line/test")
async def test_line_notification(token: Optional[str] = None):
    """Test LINE notification."""
    notifier = LineNotifier(token=token)
    success = await notifier.test_connection()
    if not success:
        raise HTTPException(status_code=400, detail="LINE notification failed. Check token.")
    return {"success": True, "data": {"message": "Test notification sent successfully"}}


@router.get("/settings")
async def get_notification_settings():
    """Get notification settings."""
    # In production, load from DB per user
    return {
        "success": True,
        "data": {
            "price_alert": True,
            "technical_signal": True,
            "ai_prediction": True,
            "ai_confidence_threshold": 0.7,
        },
    }


@router.put("/settings")
async def update_notification_settings(settings: NotificationSettings):
    """Update notification settings."""
    # In production, save to DB
    return {"success": True, "data": {"message": "Settings updated"}}
