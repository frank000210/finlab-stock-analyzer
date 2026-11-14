"""事件研究台 API：事件日曆、事件簡報、價格反應、論點抽取。

- 讀取（日曆、簡報、模板、格式檢查）不用登入；日曆與簡報在 Mongo 壞掉時仍會回內建資料。
- 新增／修改／刪除簡報與自訂日曆事件需要管理員 token。
- 價格反應會打 FinMind（每檔 1 次），結果快取 6 小時；抓不齊時只快取 30 分鐘，
  避免額度用盡時被連續重打。
- 論點抽取會呼叫 LLM，套用全站的 per-IP 節流；輸入不合格時不消耗節流額度。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from ..analysis import event_desk as ed
from ..llm import LLMUnavailable, check_llm_rate_limit
from .admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/events", tags=["events"])

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _ok(data: Any) -> dict:
    return {"success": True, "data": jsonable_encoder(data)}


async def _db_or_none():
    try:
        from ..db.mongodb import get_mongodb

        return await get_mongodb()
    except Exception:  # noqa: BLE001
        return None


async def _db_required():
    db = await _db_or_none()
    if db is None:
        raise HTTPException(status_code=503, detail="資料庫目前無法使用，請稍後再試。")
    return db


async def _custom_events(db) -> list[dict]:
    if db is None:
        return []
    out = []
    try:
        async for doc in db[ed.CAL_COLL].find({}):
            doc.pop("_id", None)
            try:
                out.append(ed.CalendarEvent.model_validate(doc).model_dump())
            except Exception:  # noqa: BLE001
                logger.warning("ev_calendar 有格式不合的事件，略過：%s", doc.get("id"))
    except Exception:  # noqa: BLE001
        logger.exception("讀取 ev_calendar 失敗，只回內建日曆")
    return out


# ─────────────────────────── 日曆 ───────────────────────────

@router.get("/calendar")
async def get_calendar(
    start: Optional[str] = Query(default=None, pattern=_DATE_PATTERN),
    end: Optional[str] = Query(default=None, pattern=_DATE_PATTERN),
    category: Optional[str] = Query(default=None, max_length=120, description="逗號分隔的類別代碼"),
):
    """事件日曆。預設回「3 天前～120 天後」；範圍最長 400 天。"""
    today = ed.tw_today()
    try:
        s = date.fromisoformat(start) if start else today - timedelta(days=3)
        e = date.fromisoformat(end) if end else today + timedelta(days=120)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期不存在（例如 2 月 30 日）。")
    wanted = None
    if category:
        wanted = {c.strip() for c in category.split(",") if c.strip()}
        unknown = wanted - set(ed.CATEGORIES)
        if unknown:
            raise HTTPException(status_code=400, detail=f"沒有這個類別：{'、'.join(sorted(unknown))}")

    db = await _db_or_none()
    briefs = await ed.list_briefs(db)
    events = ed.build_calendar(s, e, await _custom_events(db), briefs, today)
    if wanted is not None:
        events = [x for x in events if x["category"] in wanted]
    meta = ed.calendar_meta()
    meta.update({"start": min(s, e).isoformat(), "end": max(s, e).isoformat(), "today": today.isoformat()})
    return _ok({"events": events, "meta": meta})


@router.post("/calendar", dependencies=[Depends(require_admin)])
async def add_custom_event(payload: ed.CustomEventIn = Body(...)):
    """新增自訂事件（例如某檔股票的法說會日期）。同一天同標題視為同一筆。"""
    db = await _db_required()
    doc = ed.custom_event_doc(payload)
    await db[ed.CAL_COLL].update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)
    return _ok(doc)


@router.delete("/calendar/{event_id}", dependencies=[Depends(require_admin)])
async def delete_custom_event(event_id: str):
    if not event_id.startswith("c-"):
        raise HTTPException(status_code=400, detail="只能刪除自訂事件；內建與規則推算的事件隨程式版本維護。")
    db = await _db_required()
    res = await db[ed.CAL_COLL].delete_one({"_id": event_id})
    if not getattr(res, "deleted_count", 0):
        raise HTTPException(status_code=404, detail="找不到這個自訂事件。")
    return _ok({"deleted": event_id})


# ─────────────────────────── 簡報 ───────────────────────────

@router.get("/briefs")
async def list_briefs():
    briefs = await ed.list_briefs(await _db_or_none())
    return _ok([ed.brief_summary(b) for b in briefs])


@router.get("/briefs/template")
async def brief_template():
    """空白模板＋欄位說明，給編輯器當起點。"""
    return _ok({
        "template": ed.brief_template(),
        "guide": {
            "tier": "事實的來源分級：1＝官方第一手（公告、財報、交易所資料）、2＝媒體報導、3＝評論／社群／影片",
            "confirmed": "false＝有人這樣報導或這樣說，但沒有官方或當事人證實",
            "order": "影響的階數：1＝直接、2＝供應鏈與客戶、3＝資金面／評價／政策外溢",
            "direction": "benefit 受益、hurt 受害、mixed 有好有壞、unclear 還看不出來",
            "tw_base_date": "台股「事件前最後一個交易日」。美國時間發生的事，通常就是事件當天的台股收盤日",
            "episode_start": "事件前就開始發酵的那一天（選填），用來看事前已經跌／漲了多少",
        },
    })


@router.post("/briefs/validate")
async def validate_brief(payload: dict = Body(...)):
    """只檢查格式與完整度，不存檔。"""
    brief, errors = ed.validate_brief(payload)
    if brief is None:
        return _ok({"valid": False, "errors": errors[:30], "quality": None})
    return _ok({"valid": True, "errors": [], "quality": ed.brief_quality(brief)})


@router.get("/briefs/{brief_id}")
async def get_brief(brief_id: str):
    brief = await ed.get_brief(brief_id, await _db_or_none())
    if brief is None:
        raise HTTPException(status_code=404, detail="找不到這份事件簡報。")
    symbols, _ = ed.reaction_targets(brief)
    return _ok({
        "brief": brief,
        "quality": ed.brief_quality(brief),
        "reaction_available": bool(brief.get("tw_base_date") and symbols),
        "reaction_symbol_count": len(symbols),
    })


@router.put("/briefs/{brief_id}", dependencies=[Depends(require_admin)])
async def put_brief(brief_id: str, payload: dict = Body(...)):
    brief, errors = ed.validate_brief(payload)
    if brief is None:
        raise HTTPException(status_code=422, detail={"message": "簡報格式不正確", "errors": errors[:30]})
    if brief["id"] != brief_id:
        raise HTTPException(status_code=400, detail="網址上的 id 與內容裡的 id 不一致。")
    db = await _db_required()
    try:
        saved = await ed.save_brief(brief, db)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _ok({"brief": saved, "quality": ed.brief_quality(saved)})


@router.delete("/briefs/{brief_id}", dependencies=[Depends(require_admin)])
async def delete_brief(brief_id: str):
    db = await _db_required()
    try:
        deleted = await ed.delete_brief(brief_id, db)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="找不到這份事件簡報。")
    return _ok({"deleted": brief_id})


@router.get("/briefs/{brief_id}/reaction")
async def brief_reaction(brief_id: str):
    """影響地圖裡的台股標的，事件前後的漲跌、相對大盤、量能與均線位置。"""
    brief = await ed.get_brief(brief_id, await _db_or_none())
    if brief is None:
        raise HTTPException(status_code=404, detail="找不到這份事件簡報。")
    symbols, _ = ed.reaction_targets(brief)
    sig = hashlib.sha1(
        f"{brief.get('tw_base_date')}|{brief.get('episode_start')}|{','.join(symbols)}".encode("utf-8")
    ).hexdigest()[:12]
    cache_key = f"event_reaction:v1:{brief_id}:{ed.tw_today().isoformat()}:{sig}"

    try:
        from ..db.cache import get_cache, set_cache
    except Exception:  # noqa: BLE001
        get_cache = set_cache = None
    if get_cache is not None:
        try:
            cached = await get_cache(cache_key)
            if cached:
                return _ok({**cached, "cached": True})
        except Exception:  # noqa: BLE001
            pass

    try:
        result = await ed.fetch_reaction(brief)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("event reaction failed for %s", brief_id)
        raise HTTPException(status_code=502, detail="價格資料取得失敗，請稍後再試。") from exc

    if set_cache is not None:
        try:
            await set_cache(cache_key, result, "event_reaction" if result.get("complete") else "stock_price")
        except Exception:  # noqa: BLE001
            pass
    return _ok({**result, "cached": False})


# ─────────────────────────── 論點抽取 ───────────────────────────

class ClaimsRequest(BaseModel):
    text: str = Field(default="", max_length=ed.CLAIMS_MAX_CHARS + 2000)
    source: str = Field(default="", max_length=80)


@router.post("/claims/extract")
async def extract_claims(request: Request, payload: ClaimsRequest = Body(...)):
    """把影片逐字稿或文章拆成可檢驗的論點（附原句，後端核對原句是否真的出現在原文）。"""
    try:
        text = ed.check_claims_input(payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # 輸入合格才計入 per-IP 節流：貼太短／太長被擋下的不該吃掉使用者的額度
    await check_llm_rate_limit(request)
    try:
        return _ok(await ed.extract_claims(text, payload.source))
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError:
        logger.warning("event claims: LLM 回應無法解析成 JSON")
        raise HTTPException(status_code=502, detail="AI 回傳的格式無法解析，請再試一次。")
    except Exception as exc:  # noqa: BLE001
        logger.exception("event claims extract failed")
        raise HTTPException(status_code=500, detail="論點抽取失敗，請稍後再試。") from exc
