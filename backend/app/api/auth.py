"""Admin authentication API endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

try:
    from ..db.cache import get_setting
except Exception:
    get_setting = None

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class GoogleVerifyPayload(BaseModel):
    id_token: str


class LogoutPayload(BaseModel):
    ok: bool = True


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


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def _decode_token(token: str) -> dict:
    try:
        import jwt

        return jwt.decode(token, _get_secret(), algorithms=["HS256"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token.") from exc


@router.post("/google/verify")
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


@router.get("/me")
async def get_me(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    token = _extract_bearer_token(authorization)
    payload = _decode_token(token)
    return {
        "email": payload.get("email", ""),
        "name": payload.get("name", ""),
        "avatar": payload.get("avatar", ""),
        "is_admin": bool(payload.get("is_admin", False)),
    }


@router.post("/logout")
async def logout() -> LogoutPayload:
    return LogoutPayload()
