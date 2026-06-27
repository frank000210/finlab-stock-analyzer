"""Settings API endpoints with MongoDB storage."""

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
    default_stock: Optional[str] = None
    default_stock_name: Optional[str] = None


@router.get("")
async def get_settings():
    """Get app settings from MongoDB."""
    try:
        from ..db.cache import get_all_settings
        settings = await get_all_settings()
        if settings:
            return {"success": True, "data": settings}
    except Exception:
        pass

    # Fallback defaults
    return {
        "success": True,
        "data": {
            "default_period": "1Y",
            "default_indicators": ["ma", "rsi", "volume"],
            "default_strategy": "ma_crossover",
            "default_capital": 1_000_000,
            "default_stock": "2330",
            "default_stock_name": "台積電",
        },
    }


@router.put("")
async def update_settings(settings: AppSettings):
    """Update app settings to MongoDB."""
    try:
        from ..db.cache import set_setting
        data = settings.model_dump(exclude_none=True)
        for key, value in data.items():
            await set_setting(key, value)
        return {"success": True, "data": {"message": "設定已儲存"}}
    except Exception as e:
        return {"success": False, "error": f"儲存失敗: {str(e)}"}


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
