"""Admin management API endpoints."""

from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ..config.settings import get_settings
from ..notify import LineNotifier, send_telegram

try:
    from ..db.cache import get_all_settings, get_setting, set_setting
except Exception:
    get_all_settings = None
    get_setting = None
    set_setting = None

try:
    from ..db.mongodb import get_mongodb
except Exception:
    get_mongodb = None

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class SettingValuePayload(BaseModel):
    value: Any


class SettingCreatePayload(BaseModel):
    key: str
    value: Any


class AllowedAdminPayload(BaseModel):
    email: str


class TestNotificationPayload(BaseModel):
    channel: Literal["telegram", "line"]
    message: str


async def _get_db():
    if get_mongodb is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable right now.")
    try:
        return await get_mongodb()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB is unavailable: {exc}") from exc


def _get_secret() -> str:
    return get_settings().admin_secret


def _normalize_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Missing admin token.")
    parts = token.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return token.strip()


async def require_admin(token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> dict:
    try:
        import jwt

        payload = jwt.decode(_normalize_token(token), _get_secret(), algorithms=["HS256"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token.") from exc

    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return payload


def _serialize_document(doc: dict) -> dict:
    serialized = jsonable_encoder(doc)
    if "_id" in doc:
        serialized["_id"] = str(doc["_id"])
    return serialized


async def _ensure_setting_helpers_available() -> None:
    if get_setting is None or set_setting is None or get_all_settings is None:
        raise HTTPException(status_code=503, detail="MongoDB settings helpers are unavailable right now.")


async def _get_allowed_admins_value() -> list[str]:
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


@router.get("/logs")
async def get_logs(
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    type: Optional[str] = Query(default=None),
    _admin: dict = Depends(require_admin),
):
    db = await _get_db()
    query = {"type": type} if type else {}
    cursor = db.user_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    logs = []
    async for doc in cursor:
        logs.append(_serialize_document(doc))
    return {"success": True, "data": logs}


@router.get("/logs/stats")
async def get_log_stats(_admin: dict = Depends(require_admin)):
    db = await _get_db()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_visitors = await db.user_logs.distinct(
        "ip",
        {"type": "pageview", "timestamp": {"$gte": today_start}},
    )
    unique_visitors = await db.user_logs.distinct("ip", {"type": "pageview"})
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$count"}}}]
    pageview_totals = [doc async for doc in db.pageviews.aggregate(pipeline)]
    total_pageviews = int(pageview_totals[0]["total"]) if pageview_totals else 0
    return {
        "success": True,
        "data": {
            "todays_visitors": len([ip for ip in today_visitors if ip]),
            "total_pageviews": total_pageviews,
            "unique_visitors": len([ip for ip in unique_visitors if ip]),
        },
    }


@router.get("/settings")
async def get_settings_list(_admin: dict = Depends(require_admin)):
    await _ensure_setting_helpers_available()
    try:
        return {"success": True, "data": await get_all_settings()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load settings: {exc}") from exc


@router.put("/settings/{key}")
async def update_setting(key: str, payload: SettingValuePayload, _admin: dict = Depends(require_admin)):
    await _ensure_setting_helpers_available()
    try:
        await set_setting(key, payload.value)
        return {"success": True, "data": {"key": key, "value": payload.value}}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to update setting: {exc}") from exc


@router.post("/settings")
async def create_setting(payload: SettingCreatePayload, _admin: dict = Depends(require_admin)):
    db = await _get_db()
    existing = await db.settings.find_one({"key": payload.key}, {"_id": 1})
    if existing:
        raise HTTPException(status_code=400, detail=f"Setting '{payload.key}' already exists.")
    await db.settings.insert_one(
        {"key": payload.key, "value": payload.value, "updated_at": datetime.utcnow()}
    )
    return {"success": True, "data": {"key": payload.key, "value": payload.value}}


@router.delete("/settings/{key}")
async def delete_setting(key: str, _admin: dict = Depends(require_admin)):
    db = await _get_db()
    result = await db.settings.delete_one({"key": key})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' was not found.")
    return {"success": True, "data": {"key": key}}


@router.get("/allowed-admins")
async def get_allowed_admins(_admin: dict = Depends(require_admin)):
    return {"success": True, "data": await _get_allowed_admins_value()}


@router.post("/allowed-admins")
async def add_allowed_admin(payload: AllowedAdminPayload, _admin: dict = Depends(require_admin)):
    await _ensure_setting_helpers_available()
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    emails = await _get_allowed_admins_value()
    if email not in emails:
        emails.append(email)
        await set_setting("allowed_admin_emails", emails)
    return {"success": True, "data": emails}


@router.delete("/allowed-admins/{email}")
async def remove_allowed_admin(email: str, _admin: dict = Depends(require_admin)):
    await _ensure_setting_helpers_available()
    target_email = email.strip().lower()
    emails = [item for item in await _get_allowed_admins_value() if item != target_email]
    await set_setting("allowed_admin_emails", emails)
    return {"success": True, "data": emails}


@router.post("/notify/test")
async def send_test_notification(payload: TestNotificationPayload, _admin: dict = Depends(require_admin)):
    settings = get_settings()
    if payload.channel == "telegram":
        bot_token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id
        if get_setting is not None:
            try:
                bot_token = await get_setting("TELEGRAM_BOT_TOKEN", bot_token)
                chat_id = await get_setting("TELEGRAM_CHAT_ID", chat_id)
            except Exception:
                pass
        if not bot_token or not chat_id:
            raise HTTPException(status_code=400, detail="Telegram settings are not configured.")
        success = await send_telegram(payload.message, str(bot_token), str(chat_id))
    else:
        line_token = settings.line_notify_token
        if get_setting is not None:
            try:
                line_token = await get_setting("line_notify_token", line_token)
                if not line_token:
                    line_token = await get_setting("line_token", line_token)
            except Exception:
                pass
        if not line_token:
            raise HTTPException(status_code=400, detail="LINE Notify token is not configured.")
        success = await LineNotifier(token=str(line_token)).send(payload.message)

    if not success:
        raise HTTPException(status_code=502, detail=f"Failed to send {payload.channel} notification.")
    return {"success": True, "data": {"ok": True, "channel": payload.channel}}
