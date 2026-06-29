"""Analytics API endpoints backed by MongoDB."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

try:
    from ..db.mongodb import get_mongodb
except Exception:
    get_mongodb = None

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class PageViewPayload(BaseModel):
    page: str
    symbol: Optional[str] = None


class UserIdentifyPayload(BaseModel):
    email: str
    name: str
    avatar: Optional[str] = None


async def _get_db():
    if get_mongodb is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable right now.")
    try:
        return await get_mongodb()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB is unavailable: {exc}") from exc


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _insert_user_log(db, payload: dict) -> None:
    await db.user_logs.insert_one(payload)


@router.post("/pageview")
async def track_pageview(payload: PageViewPayload, request: Request):
    db = await _get_db()
    now = datetime.utcnow()
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


@router.get("/pageviews")
async def get_pageviews():
    db = await _get_db()
    pageviews = {}
    async for doc in db.pageviews.find({}, {"_id": 0, "page": 1, "count": 1}):
        pageviews[doc["page"]] = int(doc.get("count", 0))
    return pageviews


@router.get("/pageviews/{page}")
async def get_pageview_count(page: str):
    db = await _get_db()
    doc = await db.pageviews.find_one({"page": page}, {"_id": 0, "count": 1})
    return {"page": page, "count": int((doc or {}).get("count", 0))}


@router.post("/user-identify")
async def identify_user(payload: UserIdentifyPayload, request: Request):
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
            "timestamp": datetime.utcnow(),
        },
    )
    return {"ok": True, "email": payload.email}
