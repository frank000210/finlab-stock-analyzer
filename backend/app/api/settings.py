"""Settings API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..crawler import FinMindClient

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class AppSettings(BaseModel):
    finmind_token: Optional[str] = None
    line_token: Optional[str] = None
    default_period: str = "1Y"
    default_indicators: list[str] = ["ma", "rsi", "volume"]
    default_strategy: str = "ma_crossover"
    default_capital: float = 1_000_000


@router.get("")
async def get_settings():
    """Get app settings."""
    # In production, load from DB
    return {
        "success": True,
        "data": {
            "default_period": "1Y",
            "default_indicators": ["ma", "rsi", "volume"],
            "default_strategy": "ma_crossover",
            "default_capital": 1_000_000,
        },
    }


@router.put("")
async def update_settings(settings: AppSettings):
    """Update app settings."""
    return {"success": True, "data": {"message": "Settings updated"}}


@router.post("/validate-token")
async def validate_token(token_type: str, token: str):
    """Validate a third-party token."""
    if token_type == "finmind":
        try:
            client = FinMindClient(token=token)
            df = await client.get_stock_info()
            valid = not df.empty
        except Exception:
            valid = False
    elif token_type == "line":
        from ..notify import LineNotifier
        notifier = LineNotifier(token=token)
        valid = await notifier.test_connection()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown token type: {token_type}")

    return {"success": True, "data": {"valid": valid, "token_type": token_type}}
