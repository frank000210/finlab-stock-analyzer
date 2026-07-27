"""Settings API endpoints with MongoDB storage."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..crawler import FinMindClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# MM4：跟 LL3（notifications.py 的 line/test）同一種漏洞——這支端點讓呼叫端
# 自己傳入任意 FinMind/LINE token 並回報有效與否，等於公開無驗證的「token
# 有效性 oracle」，且比 LL3 涵蓋範圍更廣（同時擋 FinMind 跟 LINE 兩種）。
# 合法用途（設定頁「驗證」按鈕）需要接受任意 token，不能直接擋掉，比照
# LL3 加頻率限制。
_VALIDATE_TOKEN_WINDOW_MINUTES = 10
_VALIDATE_TOKEN_MAX_CALLS = 10


async def _check_validate_token_rate_limit(request: Request) -> None:
    from ..api.analytics import _get_client_ip
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    try:
        count = await increment_rate_limit(f"validate_token_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _VALIDATE_TOKEN_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"驗證請求過於頻繁，請 {_VALIDATE_TOKEN_WINDOW_MINUTES} 分鐘後再試。",
        )

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

# HH1：GG1 只補了讀取端（GET）的過濾，寫入端（PUT）當時沒有一併檢查——
# update_settings() 原本會把 AppSettings 裡任何非 None 欄位（含
# finmind_token/line_token）原樣寫進同一個 Mongo settings collection，
# 且這支端點沒有掛驗證。admin.py 的 send_test_notification 會把
# "line_token" 這個 key 當成 LINE 測試通知的備援來源
# （AdminView.vue 的設定編輯畫面也是直接把這個 key 當成正典欄位顯示），
# 等於任何匿名呼叫者都能用這支端點把管理員的 LINE 測試通知目標偷樑換柱。
# SettingsView.vue 的 save() 目前只送 default_period/default_capital，
# 限制成這份白名單不會影響任何既有前端行為。
_WRITABLE_SETTING_KEYS = (
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
        # II9：Mongo 讀取失敗時原本完全沒有 log，只會靜靜掉到下面的預設值
        # ——使用者感覺不到異狀（畫面正常顯示預設設定），但 Mongo 若真的
        # 掛了，這是唯一會留下痕跡的地方。
        logger.exception("get_settings: failed to read from MongoDB, falling back to defaults")

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
    """Update app settings to MongoDB (writable-safe subset only — see _WRITABLE_SETTING_KEYS)."""
    try:
        from ..db.cache import set_setting
        data = settings.model_dump(exclude_none=True)
        for key, value in data.items():
            if key not in _WRITABLE_SETTING_KEYS:
                continue
            await set_setting(key, value)
        return {"success": True, "data": {"message": "設定已儲存"}}
    except Exception as e:
        logger.exception("update_settings failed")
        return {"success": False, "error": f"儲存失敗: {str(e)}"}


class TokenValidationRequest(BaseModel):
    """Token 驗證請求。token 走 request body,避免出現在 URL/存取日誌。"""

    token_type: str
    token: str


@router.post("/validate-token", dependencies=[Depends(_check_validate_token_rate_limit)])
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
