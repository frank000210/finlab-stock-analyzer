import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/api", tags=["auth"])

# NN1: brute-force guard for /api/login. In-memory is fine -- this is a
# single-instance personal tool, not a horizontally-scaled service.
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_failed_attempts: dict[str, list[float]] = {}


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _register_failure(key: str) -> None:
    now = time.monotonic()
    attempts = [t for t in _failed_attempts.get(key, []) if now - t < _WINDOW_SECONDS]
    attempts.append(now)
    _failed_attempts[key] = attempts


def _is_locked_out(key: str) -> bool:
    now = time.monotonic()
    attempts = [t for t in _failed_attempts.get(key, []) if now - t < _WINDOW_SECONDS]
    _failed_attempts[key] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


class LoginPayload(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginPayload, request: Request) -> LoginResponse:
    settings = get_settings()
    key = _client_key(request)

    if _is_locked_out(key):
        raise HTTPException(
            status_code=429,
            detail=f"登入失敗次數過多，請在 {_WINDOW_SECONDS // 60} 分鐘後再試。",
        )

    if not settings.kb_web_password or payload.password != settings.kb_web_password:
        _register_failure(key)
        raise HTTPException(status_code=401, detail="Incorrect password.")

    _failed_attempts.pop(key, None)
    token = jwt.encode(
        {"sub": "web-user", "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return LoginResponse(token=token)
