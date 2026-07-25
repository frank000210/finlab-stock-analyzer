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
