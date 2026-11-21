"""Local FastAPI + SSE server for Frank Portal Agent Work Dashboard (backed by local MongoDB)."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import db_store

WRITE_TOKEN = os.environ.get("AGENT_DASHBOARD_WRITE_TOKEN", "").strip()
ALT_ADMIN_TOKEN = os.environ.get("AGENT_DASHBOARD_ALT_TOKEN", "").strip()


def _token_ok(provided: str) -> bool:
    if not WRITE_TOKEN and not ALT_ADMIN_TOKEN:
        return True
    val = provided.strip()
    if not val:
        return False
    if WRITE_TOKEN and hmac.compare_digest(val, WRITE_TOKEN):
        return True
    if ALT_ADMIN_TOKEN and hmac.compare_digest(val, ALT_ADMIN_TOKEN):
        return True
    return False


def require_write(request: Request) -> None:
    if not WRITE_TOKEN and not ALT_ADMIN_TOKEN:
        return
    provided = request.headers.get("X-Dashboard-Token", "")
    if not _token_ok(provided):
        raise HTTPException(status_code=401, detail="請先輸入管理金鑰解鎖編輯權限")

BASE_DIR = Path(__file__).resolve().parent
STATIC_ALLOWLIST = {
    "index.html",
    "styles.css",
    "app.js",
    "sprites-pixel.js",
    "sprites-notebook.js",
    "simulab-engine.js",
    "simulab-materials.js",
    "stage-simulab.js",
    "anatomy-inspector.js",
    "dashboard-data.js",
    "dashboard-data.json",
}

_subscribers: set[asyncio.Queue[str]] = set()
_last_known_revision: int = -1
_watcher_task: Optional[asyncio.Task] = None


def _format_sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


async def _broadcast_state(force: bool = False) -> None:
    global _last_known_revision
    meta = await asyncio.to_thread(db_store.get_meta_brief)
    rev = int(meta.get("revision", 0))
    if not force and rev == _last_known_revision:
        return
    _last_known_revision = rev
    if not _subscribers:
        return
    state = await asyncio.to_thread(db_store.get_state, False)
    msg = _format_sse(
        "state_changed",
        {
            "revision": rev,
            "event": meta.get("lastEvent"),
            "state": state,
        },
    )
    dead: list[asyncio.Queue[str]] = []
    for q in list(_subscribers):
        try:
            if q.full():
                q.get_nowait()
            q.put_nowait(msg)
        except Exception:
            dead.append(q)
    for q in dead:
        _subscribers.discard(q)


async def _watch_mongo_revision() -> None:
    global _last_known_revision
    while True:
        try:
            await _broadcast_state(force=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(1.5)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _last_known_revision, _watcher_task
    await asyncio.to_thread(db_store.ensure_indexes)
    await asyncio.to_thread(db_store.seed_from_json, False)
    await asyncio.to_thread(db_store.sync_default_agents)
    meta = await asyncio.to_thread(db_store.get_meta_brief)
    _last_known_revision = int(meta.get("revision", 0))
    _watcher_task = asyncio.create_task(_watch_mongo_revision())
    try:
        yield
    finally:
        if _watcher_task:
            _watcher_task.cancel()
            try:
                await _watcher_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Frank Agent Dashboard (Local MongoDB)", lifespan=lifespan)


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    agentId: str = "foreman"
    description: str = ""
    status: str = "todo"
    priority: str = "P1"
    site: str = "全局"
    branch: str = "待開 worktree"
    tags: list[str] = Field(default_factory=list)
    dispatch: str = "manual"
    notify: bool = True


class UpdateTaskRequest(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    agentId: Optional[str] = None
    priority: Optional[str] = None
    site: Optional[str] = None
    branch: Optional[str] = None
    tags: Optional[list[str]] = None
    dispatch: Optional[str] = None
    note: Optional[str] = None
    agentStatus: Optional[str] = None
    agentText: Optional[str] = None
    notify: bool = True


class UpdateAgentRequest(BaseModel):
    status: Optional[str] = None
    statusText: Optional[str] = None
    worktree: Optional[str] = None
    note: Optional[str] = None
    notify: bool = True


class ApproveTaskRequest(BaseModel):
    note: Optional[str] = None
    notify: bool = True


class RejectTaskRequest(BaseModel):
    note: str = ""
    requeue: bool = False
    notify: bool = True


class ClaimTaskRequest(BaseModel):
    note: Optional[str] = None
    notify: bool = True


class SaveReportRequest(BaseModel):
    markdown: str = Field(..., min_length=1)


class CreateLogRequest(BaseModel):
    agentId: str = "foreman"
    action: str = "通知"
    message: str = Field(..., min_length=1, max_length=500)
    taskId: Optional[str] = None
    notify: bool = True


@app.get("/api/health")
async def api_health(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    try:
        info = await asyncio.to_thread(db_store.ping_mongo)
        info["sseClients"] = len(_subscribers)
        info["writeProtected"] = bool(WRITE_TOKEN)
        return info
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB unreachable: {exc}")


@app.get("/api/auth/status")
async def api_auth_status(request: Request):
    provided = request.headers.get("X-Dashboard-Token", "")
    return {
        "writeProtected": bool(WRITE_TOKEN),
        "unlocked": _token_ok(provided),
        "storage": db_store.STORAGE_LABEL,
    }


@app.post("/api/auth/verify")
async def api_auth_verify(request: Request):
    provided = request.headers.get("X-Dashboard-Token", "")
    if not _token_ok(provided):
        raise HTTPException(status_code=401, detail="管理金鑰錯誤")
    return {"ok": True, "unlocked": True}


@app.get("/api/state")
async def api_state():
    try:
        return await asyncio.to_thread(db_store.get_state, True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to read MongoDB: {exc}")


@app.get("/api/events")
async def api_events(request: Request):
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=16)
    _subscribers.add(queue)

    async def event_stream():
        try:
            meta = await asyncio.to_thread(db_store.get_meta_brief)
            yield _format_sse(
                "hello",
                {
                    "revision": int(meta.get("revision", 0)),
                    "db": db_store.DB_NAME,
                },
            )
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _subscribers.discard(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/dispatch/queue")
async def api_dispatch_queue():
    tasks = await asyncio.to_thread(db_store.list_queued_tasks)
    return {"count": len(tasks), "tasks": tasks}


@app.get("/api/tasks/{task_id}/report")
async def api_get_task_report(task_id: str):
    try:
        return await asyncio.to_thread(db_store.get_task_report, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/tasks", dependencies=[Depends(require_write)])
async def api_create_task(payload: CreateTaskRequest):
    try:
        result = await asyncio.to_thread(
            db_store.add_task,
            title=payload.title,
            agent_id=payload.agentId,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            site=payload.site,
            branch=payload.branch,
            tags=payload.tags,
            dispatch=payload.dispatch,
            notify=payload.notify,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.patch("/api/tasks/{task_id}", dependencies=[Depends(require_write)])
async def api_update_task(task_id: str, payload: UpdateTaskRequest):
    try:
        result = await asyncio.to_thread(
            db_store.update_task,
            task_id,
            status=payload.status,
            title=payload.title,
            description=payload.description,
            agent_id=payload.agentId,
            priority=payload.priority,
            site=payload.site,
            branch=payload.branch,
            tags=payload.tags,
            dispatch=payload.dispatch,
            note=payload.note,
            agent_status=payload.agentStatus,
            agent_text=payload.agentText,
            notify=payload.notify,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.post("/api/tasks/{task_id}/claim", dependencies=[Depends(require_write)])
async def api_claim_task(task_id: str, payload: Optional[ClaimTaskRequest] = None):
    req = payload or ClaimTaskRequest()
    try:
        result = await asyncio.to_thread(db_store.claim_task, task_id, note=req.note, notify=req.notify)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.put("/api/tasks/{task_id}/report", dependencies=[Depends(require_write)])
async def api_save_task_report(task_id: str, payload: SaveReportRequest):
    try:
        result = await asyncio.to_thread(db_store.save_task_report, task_id, payload.markdown)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.post("/api/tasks/{task_id}/approve", dependencies=[Depends(require_write)])
async def api_approve_task(task_id: str, payload: Optional[ApproveTaskRequest] = None):
    req = payload or ApproveTaskRequest()
    try:
        result = await asyncio.to_thread(
            db_store.approve_task,
            task_id,
            note=req.note,
            notify=req.notify,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.post("/api/tasks/{task_id}/reject", dependencies=[Depends(require_write)])
async def api_reject_task(task_id: str, payload: Optional[RejectTaskRequest] = None):
    req = payload or RejectTaskRequest()
    try:
        result = await asyncio.to_thread(
            db_store.reject_task,
            task_id,
            note=req.note,
            requeue=req.requeue,
            notify=req.notify,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.delete("/api/tasks/{task_id}", dependencies=[Depends(require_write)])
async def api_delete_task(task_id: str):
    try:
        result = await asyncio.to_thread(db_store.delete_task, task_id, notify=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.post("/api/agents", dependencies=[Depends(require_write)])
async def api_upsert_agent(request: Request):
    body = await request.json()
    try:
        result = await asyncio.to_thread(db_store.upsert_agent, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.patch("/api/agents/{agent_id}", dependencies=[Depends(require_write)])
async def api_update_agent(agent_id: str, payload: UpdateAgentRequest):
    try:
        result = await asyncio.to_thread(
            db_store.update_agent,
            agent_id,
            status=payload.status,
            status_text=payload.statusText,
            worktree=payload.worktree,
            note=payload.note,
            notify=payload.notify,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_state(force=True)
    return result


@app.post("/api/logs", dependencies=[Depends(require_write)])
async def api_create_log(payload: CreateLogRequest):
    result = await asyncio.to_thread(
        db_store.add_log,
        agent_id=payload.agentId,
        action=payload.action,
        message=payload.message,
        task_id=payload.taskId,
        notify=payload.notify,
    )
    await _broadcast_state(force=True)
    return result


@app.post("/api/import-snapshot", dependencies=[Depends(require_write)])
async def api_import_snapshot(request: Request):
    snapshot = await request.json()
    result = await asyncio.to_thread(db_store.import_full_snapshot, snapshot)
    await _broadcast_state(force=True)
    return result


@app.get("/")
async def serve_root():
    return FileResponse(BASE_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/{filename}")
async def serve_static(filename: str):
    if filename not in STATIC_ALLOWLIST:
        raise HTTPException(status_code=404, detail="Not found")
    path = BASE_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, headers={"Cache-Control": "no-store"})
