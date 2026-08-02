"""Analytics API endpoints backed by MongoDB."""

import hmac
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator

try:
    from ..db.mongodb import get_mongodb
except Exception:
    get_mongodb = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class PageViewPayload(BaseModel):
    page: str
    symbol: Optional[str] = None


class UserIdentifyPayload(BaseModel):
    email: str
    name: str
    avatar: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v.strip()):
            raise ValueError("invalid email format")
        if len(v) > 254:
            raise ValueError("email too long")
        return v.strip().lower()

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if len(v.strip()) > 120:
            raise ValueError("name too long")
        return v.strip()


async def _get_db():
    if get_mongodb is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable right now.")
    try:
        return await get_mongodb()
    except Exception as exc:
        logger.exception("analytics._get_db failed")
        raise HTTPException(status_code=503, detail=f"MongoDB is unavailable: {exc}") from exc


def _get_client_ip(request: Request) -> str:
    # FF2：X-Forwarded-For 是客戶端可自訂送出的 header，反向代理收到後是把
    # 「自己看到的來源位址」*附加*到既有值後面，不是覆蓋——所以整條鏈最左邊
    # 的值永遠是客戶端自己宣稱的（可偽造），只有最右邊那個是站台前唯一那層
    # 受信任代理實際加上去的。原本取 split(",")[0]（最左邊）等於直接採信
    # 使用者自報的 IP，任何人只要每次都換一個 X-Forwarded-For 值就能拿到全新
    # 的 per-IP 額度，讓 rate_limit.py 的節流形同虛設。改取最右邊。
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[-1].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _insert_user_log(db, payload: dict) -> None:
    await db.user_logs.insert_one(payload)


async def _require_admin_token(x_admin_token: str = Header(default="")) -> None:
    """AA10: Lightweight token gate for read-only analytics endpoints.
    Uses the same admin secret as the admin panel — no new credential needed."""
    from ..config.settings import get_settings as _gs
    expected = _gs().admin_secret
    # RR5: 使用時序安全比較防止 timing oracle 攻擊
    if not expected or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Admin token required.")


# JJ3：這兩支端點完全公開、零驗證，先前也沒有任何頻率限制——一支迴圈
# script 可以無限次呼叫，讓 user_logs 無上限成長（已另外補 TTL 索引），
# identify_user 更是能讓任何人冒充任意 email 寫進 admin 後台會看到的
# 「登入」稽核紀錄。門檻刻意設得比 LLM 節流（X1，10 分鐘 6 次）寬鬆很多
# ——正常瀏覽在 10 分鐘內換好幾十頁是合理的，這裡只是要擋掉明顯異常的
# 洗量，不是要限制正常使用。
_ANALYTICS_WINDOW_MINUTES = 10
_ANALYTICS_MAX_CALLS = 120


async def _check_analytics_rate_limit(request: Request) -> None:
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    if not ip or ip == "unknown":
        return
    try:
        count = await increment_rate_limit(f"analytics_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _ANALYTICS_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"請求過於頻繁，請 {_ANALYTICS_WINDOW_MINUTES} 分鐘後再試。",
        )


@router.post("/pageview")
async def track_pageview(payload: PageViewPayload, request: Request):
    await _check_analytics_rate_limit(request)
    db = await _get_db()
    now = datetime.now(timezone.utc)
    await db.pageviews.update_one(
        {"page": payload.page},
        {
            "$inc": {"count": 1},
            "$set": {"last_seen": now},
            "$setOnInsert": {"page": payload.page},
        },
        upsert=True,
    )
    await _insert_user_log(
        db,
        {
            "type": "pageview",
            "page": payload.page,
            "symbol": payload.symbol,
            "ip": _get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": now,
        },
    )
    return {"ok": True, "page": payload.page}


@router.get("/pageviews", dependencies=[Depends(_require_admin_token)])
async def get_pageviews():
    db = await _get_db()
    pageviews = {}
    async for doc in db.pageviews.find({}, {"_id": 0, "page": 1, "count": 1}):
        pageviews[doc["page"]] = int(doc.get("count", 0))
    return pageviews


@router.get("/pageviews/{page}", dependencies=[Depends(_require_admin_token)])
async def get_pageview_count(page: str):
    db = await _get_db()
    doc = await db.pageviews.find_one({"page": page}, {"_id": 0, "count": 1})
    return {"page": page, "count": int((doc or {}).get("count", 0))}


@router.post("/user-identify")
async def identify_user(payload: UserIdentifyPayload, request: Request):
    await _check_analytics_rate_limit(request)
    db = await _get_db()
    await _insert_user_log(
        db,
        {
            "type": "login",
            "email": payload.email,
            "name": payload.name,
            "avatar": payload.avatar,
            "ip": _get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": datetime.now(timezone.utc),
        },
    )
    return {"ok": True, "email": payload.email}
