"""Admin authentication API endpoints."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

try:
    from ..db.cache import get_setting
except Exception:
    get_setting = None

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# RR7: /google/verify 先前完全沒有頻率限制，攻擊者可批次測試 Google token
# 是否屬於本站管理員帳號。補上比照其他認證端點的 IP 節流。
_GOOGLE_VERIFY_WINDOW_MINUTES = 10
_GOOGLE_VERIFY_MAX_CALLS = 20


async def _check_google_verify_rate_limit(request: Request) -> None:
    try:
        from ..api.analytics import _get_client_ip
        from ..db.cache import increment_rate_limit
        ip = _get_client_ip(request)
        count = await increment_rate_limit(f"auth_google_verify_rate:{ip}", "rate_limit")
        if count > _GOOGLE_VERIFY_MAX_CALLS:
            raise HTTPException(
                status_code=429,
                detail=f"驗證請求過於頻繁，請 {_GOOGLE_VERIFY_WINDOW_MINUTES} 分鐘後再試。",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # 節流輔助 DB 失敗不應阻斷正常登入


# 後台改成只用 ADMIN_SECRET 密碼登入後，/direct-login 成了唯一入口，必須擋
# 暴力猜密碼。只計「失敗」次數：e2e 每輪會正確登入十幾次、pre-push 又會
# 連跑兩輪，若連成功也計數會把測試自己鎖在門外。
_DIRECT_LOGIN_WINDOW_MINUTES = 10
_DIRECT_LOGIN_MAX_FAILURES = 10


def _direct_login_rate_key(request: Request) -> str:
    from ..api.analytics import _get_client_ip
    return f"auth_direct_login_fail:{_get_client_ip(request)}"


async def _direct_login_locked(request: Request) -> bool:
    try:
        from ..db.cache import get_rate_limit_count
        return await get_rate_limit_count(_direct_login_rate_key(request)) >= _DIRECT_LOGIN_MAX_FAILURES
    except Exception:
        return False  # 節流輔助 DB 失敗不應阻斷正常登入


async def _record_direct_login_failure(request: Request) -> None:
    try:
        from ..db.cache import increment_rate_limit
        await increment_rate_limit(_direct_login_rate_key(request), "rate_limit")
    except Exception:
        pass


class GoogleVerifyPayload(BaseModel):
    id_token: str


class DirectLoginPayload(BaseModel):
    secret: str


@router.post("/direct-login")
async def direct_login(payload: DirectLoginPayload, request: Request):
    """ADMIN_SECRET 密碼登入（後台唯一的登入方式）。"""
    import hmac
    import jwt

    settings = get_settings()
    if not settings.admin_secret:
        raise HTTPException(status_code=503, detail="ADMIN_SECRET 尚未設定。")

    if await _direct_login_locked(request):
        raise HTTPException(
            status_code=429,
            detail=f"密碼錯誤次數過多，請 {_DIRECT_LOGIN_WINDOW_MINUTES} 分鐘後再試。",
        )

    if not hmac.compare_digest(payload.secret.encode(), settings.admin_secret.encode()):
        await _record_direct_login_failure(request)
        raise HTTPException(status_code=401, detail="密碼錯誤。")

    email = settings.default_allowed_admins[0] if settings.default_allowed_admins else ""
    session_token = jwt.encode(
        {
            "email": email,
            "name": "管理員",
            "avatar": "",
            "is_admin": True,
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        settings.admin_secret,
        algorithm="HS256",
    )
    return {
        "valid": True,
        "is_admin": True,
        "email": email,
        "name": "管理員",
        "avatar": "",
        "token": session_token,
    }


def _get_secret() -> str:
    return get_settings().admin_secret


async def _get_allowed_admins() -> list[str]:
    default_admins = get_settings().default_allowed_admins
    if get_setting is None:
        return default_admins
    try:
        admins = await get_setting("allowed_admin_emails", default_admins)
    except Exception:
        return default_admins
    if not isinstance(admins, list):
        return default_admins
    cleaned = [str(email).strip().lower() for email in admins if str(email).strip()]
    return cleaned or default_admins


@router.post("/google/verify", dependencies=[Depends(_check_google_verify_rate_limit)])
async def verify_google_token(payload: GoogleVerifyPayload):
    settings = get_settings()
    if not settings.google_client_id:
        return {
            "valid": False,
            "is_admin": False,
            "email": "",
            "name": "",
            "avatar": "",
            "token": "",
        }

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        import jwt
    except Exception as exc:
        # Z4：這是管理員登入端點，不回傳確切的匯入錯誤細節給呼叫端（跟下面
        # _decode_token 對 token 失敗的處理一致），只記到伺服器端日誌。
        logger.exception("admin auth dependencies unavailable")
        raise HTTPException(status_code=500, detail="Authentication is temporarily unavailable.") from exc

    try:
        token_info = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception:
        return {
            "valid": False,
            "is_admin": False,
            "email": "",
            "name": "",
            "avatar": "",
            "token": "",
        }

    email = str(token_info.get("email", "")).strip().lower()
    name = str(token_info.get("name", "")).strip()
    avatar = str(token_info.get("picture", "") or "")
    allowed_admins = await _get_allowed_admins()
    is_admin = email in allowed_admins
    session_token = jwt.encode(
        {
            "email": email,
            "name": name,
            "avatar": avatar,
            "is_admin": is_admin,
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        _get_secret(),
        algorithm="HS256",
    )
    return {
        "valid": True,
        "is_admin": is_admin,
        "email": email,
        "name": name,
        "avatar": avatar,
        "token": session_token,
    }
