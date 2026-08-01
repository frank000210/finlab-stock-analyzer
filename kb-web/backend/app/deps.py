from __future__ import annotations

from functools import lru_cache
from typing import Optional

import jwt
from fastapi import Header, HTTPException
from pymongo import MongoClient
from pymongo.database import Database

from .config import get_settings


@lru_cache
def _get_client() -> MongoClient:
    # NN3: one pooled client for the process lifetime instead of opening a
    # fresh MongoClient (and its connection pool) on every single request.
    return MongoClient(get_settings().kb_mongo_uri)


def get_db() -> Database:
    return _get_client()[get_settings().kb_mongo_db]


def require_auth(authorization: Optional[str] = Header(default=None)) -> str:
    """Returns the caller identity ('web-user' or 'cli') or raises 401."""
    settings = get_settings()
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    parts = authorization.split(" ", 1)
    token = parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else authorization.strip()

    if settings.kb_api_token and token == settings.kb_api_token:
        return "cli"

    try:
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return "web-user"
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc
