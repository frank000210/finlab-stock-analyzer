"""Settings API endpoints with MongoDB storage."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..crawler import FinMindClient

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# GG1：這支端點沒有掛任何驗證（App.vue 讀 google_client_id 給登入前的
# Google 按鈕用、SettingsView.vue 讀寫 default_period/default_capital，
# 兩個都是必須匿名可存取的正常功能，不能整支端點掛 require_admin）。但先前
# 直接呼叫 get_all_settings() 把整個 Mongo settings collection 原樣吐回去
# ——這個 collection 跟 admin.py 共用，裡面混放了 TELEGRAM_BOT_TOKEN、
# TELEGRAM_CHAT_ID、allowed_admin_emails 等管理員專用機密（admin.py 透過
# set_setting 寫入同一個 collection），等於任何匿名呼叫者都能讀到。改成
# 只回傳這個端點原本就該公開的欄位；管理員要看/改完整設定用已經掛
# require_admin 的 /api/v1/admin/settings（同一支 get_all_settings()）。
_PUBLIC_SETTING_KEYS = (
    "google_client_id",
    "default_period",
    "default_indicators",
    "default_strategy",
    "default_capital",
    "default_stock",
    "default_stock_name",
)


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
    """Get app settings from MongoDB (public-safe subset only — see _PUBLIC_SETTING_KEYS)."""
    try:
        from ..db.cache import get_setting
        settings = {}
        for key in _PUBLIC_SETTING_KEYS:
            value = await get_setting(key, None)
            if value is not None:
                settings[key] = value
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


class TokenValidationRequest(BaseModel):
    """Token 驗證請求。token 走 request body,避免出現在 URL/存取日誌。"""

    token_type: str
    token: str


@router.post("/validate-token")
async def validate_token(payload: TokenValidationRequest):
    """Validate a third-party token.(token 由 body 傳入,不走 query string)"""
    token_type, token = payload.token_type, payload.token
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
