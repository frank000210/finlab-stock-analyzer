"""學習中心 API：教材、帳號、進度、測驗、AI 助教、期末專題與證書。

身分：沿用全站同一把 JWT（X-Admin-Token header，admin_secret 簽章）。
- Google 登入（/api/v1/auth/google/verify）簽出的 token 直接可用
- 沒有 Google 帳號的學習者用這裡的 /auth/register、/auth/login 建本機帳號，
  簽出 provider=local、is_admin 固定 False 的 token

進度以 uid = "<provider>:<email>" 為鍵，而不是只用 email：任何人都能用別人的
Gmail 註冊本機帳號，如果只用 email 當鍵，搶先註冊的人就能讀寫那位 Google
使用者的學習進度。

MongoDB 集合：course_users、course_progress、course_projects。
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from ..course import accounts, content
from ..course.tutor import (
    PROJECT_REVIEW_SYSTEM,
    TUTOR_SYSTEM,
    build_project_prompt,
    build_tutor_prompt,
)
from ..llm import LLMUnavailable, is_llm_configured, llm_complete
from .admin import _get_secret, _normalize_token, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/course", tags=["course"])

_AUTH_WINDOW_MAX = 10          # 每 IP 10 分鐘內最多 10 次註冊/登入嘗試
_TUTOR_DAILY_MAX = 30          # 每位學習者每天最多問 30 次 AI 助教
_PROJECT_REVIEW_DAILY_MAX = 5  # 期末專題 AI 初評每天最多 5 次
_TOKEN_HOURS = 24 * 7

try:
    from ..db.mongodb import get_mongodb
except Exception:  # pragma: no cover
    get_mongodb = None

_indexes_ready = False


async def _db():
    global _indexes_ready
    if get_mongodb is None:
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用。")
    try:
        db = await get_mongodb()
        if not _indexes_ready:
            await db.course_users.create_index("email", unique=True)
            await db.course_progress.create_index("uid", unique=True)
            await db.course_projects.create_index("uid", unique=True)
            await db.course_projects.create_index("cert_id", sparse=True)
            _indexes_ready = True
        return db
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("course._db failed")
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用。") from exc


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 身分 ────────────────────────────────────────────────────────────────

def _decode(token: Optional[str]) -> dict | None:
    if not token:
        return None
    try:
        import jwt

        payload = jwt.decode(_normalize_token(token), _get_secret(), algorithms=["HS256"])
    except Exception:
        return None
    email = str(payload.get("email") or "").strip().lower()
    if not email:
        return None
    provider = str(payload.get("provider") or "google")
    return {
        "uid": f"{provider}:{email}",
        "email": email,
        "name": str(payload.get("name") or email.split("@")[0]),
        "provider": provider,
        "is_admin": bool(payload.get("is_admin")),
    }


async def optional_learner(token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> dict | None:
    return _decode(token)


async def require_learner(token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> dict:
    learner = _decode(token)
    if learner is None:
        raise HTTPException(status_code=401, detail="請先登入學習中心。")
    return learner


async def _rate_limit(key: str, limit: int, category: str, message: str) -> None:
    try:
        from ..db.cache import increment_rate_limit

        count = await increment_rate_limit(key, category)
    except Exception:
        return  # 節流機制故障不擋功能（同 llm/rate_limit.py）
    if count > limit:
        raise HTTPException(status_code=429, detail=message)


async def _auth_rate_limit(request: Request) -> None:
    from .analytics import _get_client_ip

    await _rate_limit(
        f"course_auth:{_get_client_ip(request)}", _AUTH_WINDOW_MAX, "rate_limit",
        "嘗試次數過多，請 10 分鐘後再試。",
    )


def _issue_token(email: str, name: str) -> str:
    import jwt

    return jwt.encode(
        {
            "email": email,
            "name": name,
            "avatar": "",
            "is_admin": False,
            "provider": "local",
            "exp": _now() + timedelta(hours=_TOKEN_HOURS),
        },
        _get_secret(),
        algorithm="HS256",
    )


class RegisterPayload(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=40)


class LoginPayload(BaseModel):
    email: str
    password: str = Field(max_length=128)


def _auth_response(email: str, name: str) -> dict:
    return {
        "valid": True, "is_admin": False, "email": email, "name": name,
        "avatar": "", "provider": "local", "token": _issue_token(email, name),
    }


@router.post("/auth/register", dependencies=[Depends(_auth_rate_limit)])
async def register(payload: RegisterPayload):
    email = accounts.normalize_email(payload.email)
    if not accounts.is_valid_email(email):
        raise HTTPException(status_code=422, detail="Email 格式不正確。")
    name = payload.name.strip() or email.split("@")[0]
    db = await _db()
    try:
        await db.course_users.insert_one({
            "email": email,
            "name": name,
            "password_hash": accounts.hash_password(payload.password),
            "created_at": _now(),
        })
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "E11000" in str(exc):
            raise HTTPException(status_code=409, detail="這個 Email 已經註冊過，請直接登入。") from exc
        raise
    return _auth_response(email, name)


@router.post("/auth/login", dependencies=[Depends(_auth_rate_limit)])
async def login(payload: LoginPayload):
    email = accounts.normalize_email(payload.email)
    db = await _db()
    user = await db.course_users.find_one({"email": email})
    # 帳號不存在跟密碼錯誤回同一句話，不讓人藉此探測哪些 Email 註冊過
    if not user or not accounts.verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email 或密碼錯誤。")
    return _auth_response(email, user.get("name") or email.split("@")[0])


# ── 教材（公開） ─────────────────────────────────────────────────────────

def _content_error(exc: content.CourseContentError) -> HTTPException:
    logger.error("course content error: %s", exc)
    return HTTPException(status_code=500, detail="教材檔案有問題，請通知管理員。")


@router.get("/catalog")
async def catalog():
    try:
        data = content.load_catalog()
    except content.CourseContentError as exc:
        raise _content_error(exc) from exc
    return {
        "title": data.get("title", ""),
        "stages": data.get("stages", []),
        "units": data["units"],
        "tutor_available": is_llm_configured(),
    }


@router.get("/units/{unit_id}")
async def unit_detail(unit_id: str):
    meta = content.get_unit_meta(unit_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="沒有這個單元。")
    try:
        body = content.load_unit_markdown(unit_id)
        quiz = content.public_quiz(content.load_quiz(unit_id))
        lab_readme = content.load_lab_readme(unit_id)
    except content.CourseContentError as exc:
        raise _content_error(exc) from exc
    ids = content.unit_ids()
    idx = ids.index(unit_id)
    return {
        "meta": meta,
        "markdown": body,
        "quiz": quiz,
        "lab_readme": lab_readme,
        "prev": ids[idx - 1] if idx > 0 else None,
        "next": ids[idx + 1] if idx + 1 < len(ids) else None,
    }


@router.get("/units/{unit_id}/lab.zip")
async def unit_lab_zip(unit_id: str):
    data = content.lab_zip_bytes(unit_id)
    if data is None:
        raise HTTPException(status_code=404, detail="這個單元沒有 lab。")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{unit_id}-lab.zip"'},
    )


@router.get("/placement")
async def placement_questions():
    try:
        return content.public_quiz(content.load_quiz("placement"))
    except content.CourseContentError as exc:
        raise _content_error(exc) from exc


# ── 進度 ────────────────────────────────────────────────────────────────

class AnswersPayload(BaseModel):
    answers: dict[str, int] = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def _bounded(cls, v: dict[str, int]) -> dict[str, int]:
        if len(v) > 100:
            raise ValueError("too many answers")
        return {str(k)[:32]: int(val) for k, val in v.items()}


async def _get_progress(db, learner: dict) -> dict:
    doc = await db.course_progress.find_one({"uid": learner["uid"]}, {"_id": 0})
    return doc or {"uid": learner["uid"], "units": {}}


async def _touch_progress(db, learner: dict, set_fields: dict, inc_fields: dict | None = None) -> None:
    update = {
        "$set": {**set_fields, "email": learner["email"], "name": learner["name"], "updated_at": _now()},
        "$setOnInsert": {"created_at": _now()},
    }
    if inc_fields:
        update["$inc"] = inc_fields
    await db.course_progress.update_one({"uid": learner["uid"]}, update, upsert=True)


def _summarize(progress: dict) -> dict:
    units = progress.get("units", {})
    required = content.required_unit_ids()
    passed_required = [u for u in required if units.get(u, {}).get("passed")]
    return {
        "units": units,
        "placement": progress.get("placement"),
        "required": required,
        "passed_required": passed_required,
        "all_required_passed": len(passed_required) == len(required),
    }


@router.post("/placement")
async def submit_placement(payload: AnswersPayload, learner: dict | None = Depends(optional_learner)):
    quiz = content.load_quiz("placement")
    if quiz is None:
        raise HTTPException(status_code=404, detail="尚未提供程度檢測。")
    result = content.grade_placement(quiz, payload.answers)
    if learner:
        db = await _db()
        await _touch_progress(db, learner, {"placement": {**result, "taken_at": _now()}})
    return result


@router.get("/me")
async def me(learner: dict = Depends(require_learner)):
    db = await _db()
    progress = await _get_progress(db, learner)
    project = await db.course_projects.find_one({"uid": learner["uid"]}, {"_id": 0, "uid": 0, "reviewed_by": 0})
    return {
        "learner": {k: learner[k] for k in ("email", "name", "provider", "is_admin")},
        "progress": _summarize(progress),
        "project": project,
        "tutor_available": is_llm_configured(),
    }


@router.post("/units/{unit_id}/quiz")
async def submit_quiz(unit_id: str, payload: AnswersPayload,
                      learner: dict | None = Depends(optional_learner)):
    if content.get_unit_meta(unit_id) is None:
        raise HTTPException(status_code=404, detail="沒有這個單元。")
    quiz = content.load_quiz(unit_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="這個單元沒有測驗。")
    result = content.grade_quiz(quiz, payload.answers)
    result["saved"] = False
    if learner:
        db = await _db()
        progress = await _get_progress(db, learner)
        prev = progress.get("units", {}).get(unit_id, {})
        best = max(prev.get("best", 0.0), result["ratio"])
        fields = {
            f"units.{unit_id}.best": best,
            f"units.{unit_id}.last": result["ratio"],
            f"units.{unit_id}.last_at": _now(),
            f"units.{unit_id}.wrong": [r["id"] for r in result["results"] if not r["correct"]],
        }
        if result["passed"] and not prev.get("passed"):
            fields[f"units.{unit_id}.passed"] = True
            fields[f"units.{unit_id}.passed_at"] = _now()
        await _touch_progress(db, learner, fields, {f"units.{unit_id}.attempts": 1})
        result["saved"] = True
        result["best"] = best
    return result


class LabPayload(BaseModel):
    done: bool = True


@router.post("/units/{unit_id}/lab")
async def mark_lab(unit_id: str, payload: LabPayload, learner: dict = Depends(require_learner)):
    meta = content.get_unit_meta(unit_id)
    if meta is None or not meta.get("lab"):
        raise HTTPException(status_code=404, detail="這個單元沒有 lab。")
    db = await _db()
    await _touch_progress(db, learner, {
        f"units.{unit_id}.lab_done": payload.done,
        f"units.{unit_id}.lab_at": _now(),
    })
    return {"ok": True, "lab_done": payload.done}


# ── AI 助教 ──────────────────────────────────────────────────────────────

class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class TutorPayload(BaseModel):
    unit_id: str
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list)


@router.post("/tutor")
async def tutor(payload: TutorPayload, learner: dict = Depends(require_learner)):
    meta = content.get_unit_meta(payload.unit_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="沒有這個單元。")
    await _rate_limit(
        f"course_tutor:{learner['uid']}:{date.today().isoformat()}",
        _TUTOR_DAILY_MAX, "course_daily",
        f"今天的 AI 助教提問已達 {_TUTOR_DAILY_MAX} 次上限，明天再來，或把問題帶到 Claude Code 問。",
    )
    history = [
        {"role": t.role, "content": t.content[:1500]}
        for t in payload.history[-6:] if t.role in ("user", "assistant")
    ]
    prompt = build_tutor_prompt(
        meta["title"], content.unit_excerpt(payload.unit_id), payload.question, history,
    )
    try:
        answer = await llm_complete(TUTOR_SYSTEM, prompt, max_tokens=1200, temperature=0.3)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"answer": answer}


# ── 期末專題與證書 ───────────────────────────────────────────────────────

class ProjectPayload(BaseModel):
    repo_url: str = Field(default="", max_length=300)
    summary: str = Field(min_length=50, max_length=6000)

    @field_validator("repo_url")
    @classmethod
    def _https_only(cls, v: str) -> str:
        v = v.strip()
        if v and not v.startswith("https://"):
            raise ValueError("repo 網址需以 https:// 開頭")
        return v


@router.post("/project")
async def submit_project(payload: ProjectPayload, learner: dict = Depends(require_learner)):
    db = await _db()
    progress = _summarize(await _get_progress(db, learner))
    if not progress["all_required_passed"]:
        missing = [u for u in progress["required"] if u not in progress["passed_required"]]
        raise HTTPException(status_code=409, detail=f"還有必修單元未通過測驗：{', '.join(missing)}")

    existing = await db.course_projects.find_one({"uid": learner["uid"]})
    if existing and existing.get("status") == "approved":
        raise HTTPException(status_code=409, detail="專題已通過審核，證書已核發。")

    ai_feedback = ""
    try:
        await _rate_limit(
            f"course_project_ai:{learner['uid']}:{date.today().isoformat()}",
            _PROJECT_REVIEW_DAILY_MAX, "course_daily", "今日 AI 初評次數已用完。",
        )
        ai_feedback = await llm_complete(
            PROJECT_REVIEW_SYSTEM,
            build_project_prompt(learner["name"], payload.repo_url, payload.summary),
            max_tokens=1000,
        )
    except (LLMUnavailable, HTTPException) as exc:
        # AI 初評只是加分項；失敗不影響送審，人工審核照常進行
        logger.info("project AI review skipped: %s", getattr(exc, "detail", exc))

    await db.course_projects.update_one(
        {"uid": learner["uid"]},
        {
            "$set": {
                "email": learner["email"], "name": learner["name"],
                "repo_url": payload.repo_url, "summary": payload.summary,
                "ai_feedback": ai_feedback, "status": "pending",
                "review_comment": "", "submitted_at": _now(),
            },
        },
        upsert=True,
    )
    return {"status": "pending", "ai_feedback": ai_feedback}


@router.get("/certificate/{cert_id}")
async def certificate(cert_id: str):
    if not cert_id.isalnum() or len(cert_id) > 32:
        raise HTTPException(status_code=404, detail="查無此證書。")
    db = await _db()
    doc = await db.course_projects.find_one({"cert_id": cert_id, "status": "approved"})
    if not doc:
        raise HTTPException(status_code=404, detail="查無此證書。")
    catalog = content.load_catalog()
    return {
        "cert_id": cert_id,
        "name": doc.get("name", ""),
        "course": catalog.get("title", ""),
        "issued_at": doc.get("reviewed_at"),
        "repo_url": doc.get("repo_url", ""),
    }


# ── 管理員 ──────────────────────────────────────────────────────────────

@router.get("/admin/learners")
async def admin_learners(_: dict = Depends(require_admin)):
    db = await _db()
    required = content.required_unit_ids()
    rows = []
    async for doc in db.course_progress.find({}, {"_id": 0}).sort("updated_at", -1).limit(500):
        units = doc.get("units", {})
        rows.append({
            "uid": doc["uid"], "email": doc.get("email"), "name": doc.get("name"),
            "passed_required": sum(1 for u in required if units.get(u, {}).get("passed")),
            "required_total": len(required),
            "placement_start": (doc.get("placement") or {}).get("recommended_start"),
            "updated_at": doc.get("updated_at"),
        })
    return {"learners": rows}


@router.get("/admin/projects")
async def admin_projects(_: dict = Depends(require_admin)):
    db = await _db()
    rows = []
    async for doc in db.course_projects.find({}, {"_id": 0}).sort("submitted_at", -1).limit(200):
        rows.append(doc)
    return {"projects": rows}


class ReviewPayload(BaseModel):
    uid: str = Field(max_length=300)
    approved: bool
    comment: str = Field(default="", max_length=2000)


@router.post("/admin/projects/review")
async def admin_review(payload: ReviewPayload, admin: dict = Depends(require_admin)):
    db = await _db()
    doc = await db.course_projects.find_one({"uid": payload.uid})
    if not doc:
        raise HTTPException(status_code=404, detail="找不到這份專題。")
    fields = {
        "status": "approved" if payload.approved else "rejected",
        "review_comment": payload.comment,
        "reviewed_at": _now(),
        "reviewed_by": admin.get("email", ""),
    }
    if payload.approved and not doc.get("cert_id"):
        fields["cert_id"] = secrets.token_hex(8)
    await db.course_projects.update_one({"uid": payload.uid}, {"$set": fields})
    return {"ok": True, **{k: v for k, v in fields.items() if k != "reviewed_by"}}
