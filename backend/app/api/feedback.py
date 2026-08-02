"""使用者意見收集：公開送出/瀏覽意見，後續自主優化循環（改善紀錄）以此為
輸入來源之一；改善完成後，透過 admin 專用的 PATCH 端點把處理結果（狀態、
回覆）寫回同一筆意見，讓使用者在原頁面就能看到自己的意見有沒有被採納。
"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, field_validator

from .admin import require_admin

try:
    from ..db.mongodb import get_mongodb
except Exception:
    get_mongodb = None

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

_CONTENT_MAX_LEN = 2000
_FEEDBACK_WINDOW_MINUTES = 10
_FEEDBACK_MAX_CALLS = 10


async def _get_db():
    if get_mongodb is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable right now.")
    try:
        return await get_mongodb()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB is unavailable: {exc}") from exc


async def _check_feedback_rate_limit(request: Request) -> None:
    from .analytics import _get_client_ip
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    if not ip or ip == "unknown":
        return
    try:
        count = await increment_rate_limit(f"feedback_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _FEEDBACK_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"送出過於頻繁，請 {_FEEDBACK_WINDOW_MINUTES} 分鐘後再試。",
        )


class FeedbackCreatePayload(BaseModel):
    content: str
    category: Literal["bug", "feature", "other"] = "other"
    page: Optional[str] = None

    @field_validator("content")
    @classmethod
    def _clean_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("內容不可空白")
        return v[:_CONTENT_MAX_LEN]

    @field_validator("page")
    @classmethod
    def _clean_page(cls, v: Optional[str]) -> Optional[str]:
        return (v or "").strip()[:200] or None


class FeedbackUpdatePayload(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    response: Optional[str] = None

    @field_validator("response")
    @classmethod
    def _clean_response(cls, v: Optional[str]) -> Optional[str]:
        return (v or "").strip()[:_CONTENT_MAX_LEN] or None


def _serialize(doc: dict) -> dict:
    serialized = jsonable_encoder(doc)
    serialized["_id"] = str(doc["_id"])
    return serialized


@router.post("", dependencies=[Depends(_check_feedback_rate_limit)])
async def create_feedback(payload: FeedbackCreatePayload):
    db = await _get_db()
    now = datetime.utcnow()
    doc = {
        "content": payload.content,
        "category": payload.category,
        "page": payload.page,
        "status": "open",
        "response": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    result = await db.feedback.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"success": True, "data": _serialize(doc)}


@router.get("")
async def list_feedback(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
):
    db = await _get_db()
    query = {"status": status} if status else {}
    cursor = db.feedback.find(query).sort("created_at", -1).skip(skip).limit(limit)
    items = [_serialize(doc) async for doc in cursor]
    return {"success": True, "data": items}


@router.patch("/{feedback_id}")
async def update_feedback(feedback_id: str, payload: FeedbackUpdatePayload, _admin: dict = Depends(require_admin)):
    from bson import ObjectId
    from bson.errors import InvalidId
    from pymongo import ReturnDocument

    db = await _get_db()
    try:
        oid = ObjectId(feedback_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid feedback id.")

    now = datetime.utcnow()
    update = {
        "status": payload.status,
        "response": payload.response,
        "updated_at": now,
    }
    if payload.status == "resolved":
        update["resolved_at"] = now

    result = await db.feedback.find_one_and_update(
        {"_id": oid},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return {"success": True, "data": _serialize(result)}
