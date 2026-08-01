from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/api", tags=["auth"])


class LoginPayload(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginPayload) -> LoginResponse:
    settings = get_settings()
    if not settings.kb_web_password or payload.password != settings.kb_web_password:
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token = jwt.encode(
        {"sub": "web-user", "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return LoginResponse(token=token)
