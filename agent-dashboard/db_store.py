"""Local MongoDB persistence, cache sync, and Windows Toast notifier for Agent Dashboard."""

from __future__ import annotations

import json
import os
import re
import subprocess
import xml.sax.saxutils as xml_utils
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient

BASE_DIR = Path(__file__).resolve().parent
JSON_CACHE_PATH = BASE_DIR / "dashboard-data.json"
JS_CACHE_PATH = BASE_DIR / "dashboard-data.js"
REPORTS_DIR = BASE_DIR / "reports"

MONGO_URI = os.environ.get("AGENT_DASHBOARD_MONGO_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.environ.get("AGENT_DASHBOARD_DB", "agent_dashboard")
STORAGE_LABEL = os.environ.get("AGENT_DASHBOARD_STORAGE_LABEL", "local")
NO_FILE_CACHE = os.environ.get("AGENT_DASHBOARD_NO_FILE_CACHE", "0") == "1"
TAIPEI_TZ = timezone(timedelta(hours=8))

STATUS_LABELS = {
    "todo": "待辦",
    "in_progress": "進行中",
    "blocked": "卡關／待核准",
    "done": "已完成",
    "working": "作業中",
    "idle": "待機",
}

VALID_TASK_STATUSES = {"todo", "in_progress", "blocked", "done"}
VALID_AGENT_STATUSES = {"working", "idle", "blocked", "done"}
VALID_PRIORITIES = {"P0", "P1", "P2"}
VALID_DISPATCH_STATES = {"manual", "queued", "dispatched"}
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}

_client: Optional[MongoClient] = None


def now_display() -> str:
    return datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")


def now_hhmm() -> str:
    return datetime.now(TAIPEI_TZ).strftime("%H:%M")


def now_iso() -> str:
    return datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return _client


def get_db():
    return get_client()[DB_NAME]


def ensure_indexes() -> None:
    db = get_db()
    db.agents.create_index([("order", ASCENDING)])
    db.tasks.create_index([("status", ASCENDING), ("order", ASCENDING)])
    db.tasks.create_index([("agentId", ASCENDING)])
    db.tasks.create_index([("updatedAt", DESCENDING)])
    db.activity_logs.create_index([("seq", DESCENDING)])


def ping_mongo() -> dict[str, Any]:
    db = get_db()
    db.command("ping")
    meta = db.meta.find_one({"_id": "singleton"}) or {}
    return {
        "ok": True,
        "mongo": "ok",
        "db": DB_NAME,
        "storage": STORAGE_LABEL,
        "revision": int(meta.get("revision", 0)),
        "updatedAt": meta.get("updatedAt", "—"),
        "counts": {
            "agents": db.agents.count_documents({}),
            "tasks": db.tasks.count_documents({}),
            "logs": db.activity_logs.count_documents({}),
        },
    }


def _next_log_seq(db) -> int:
    doc = db.activity_logs.find_one(sort=[("seq", DESCENDING)], projection={"seq": 1})
    return int(doc["seq"]) + 1 if doc and "seq" in doc else 1


def _next_task_id(db) -> str:
    max_num = 0
    for doc in db.tasks.find({}, {"id": 1}):
        tid = str(doc.get("id", ""))
        m = re.match(r"^T-(\d+)$", tid)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"T-{max_num + 1:03d}"


def _bump_meta(db, event: Optional[dict[str, Any]] = None) -> int:
    ts = now_display()
    update_set: dict[str, Any] = {"updatedAt": ts}
    if event is not None:
        update_set["lastEvent"] = event
    res = db.meta.find_one_and_update(
        {"_id": "singleton"},
        {
            "$inc": {"revision": 1},
            "$set": update_set,
            "$setOnInsert": {
                "title": "Frank 入口網站 — Agent 工作儀表板",
                "subtitle": "1 工頭 ＋ 4 入口各站 ＋ 5 FinLab 側邊欄大類專屬開發團隊",
                "portalUrl": "https://43-133-44-216.sslip.io",
                "repoPath": r"F:\github\finlab-stock-analyzer",
            },
        },
        upsert=True,
        return_document=True,
    )
    rev = int(res.get("revision", 1))
    if event is not None:
        db.meta.update_one({"_id": "singleton"}, {"$set": {"lastEvent.revision": rev}})
    return rev


def send_windows_toast(title: str, message: str) -> bool:
    """Fire a non-blocking native Windows 10/11 Toast notification via WinRT."""
    if os.name != "nt":
        return False
    safe_title = xml_utils.escape(title[:120])
    safe_msg = xml_utils.escape(message[:240])
    # Standard built-in Windows PowerShell AUMID so Toast shows cleanly without app registration
    app_id = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    ps_script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null; "
        f"$xml = '<toast><visual><binding template=\"ToastText02\"><text id=\"1\">{safe_title}</text><text id=\"2\">{safe_msg}</text></binding></visual></toast>'; "
        "$doc = New-Object Windows.Data.Xml.Dom.XmlDocument; "
        "$doc.LoadXml($xml); "
        "$toast = New-Object Windows.UI.Notifications.ToastNotification $doc; "
        f"$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}'); "
        "$notifier.Show($toast)"
    )
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return True
    except Exception:
        return False


def seed_from_json(force: bool = False) -> dict[str, Any]:
    """Import initial agents/tasks/activityLog from local dashboard-data.json into MongoDB."""
    ensure_indexes()
    db = get_db()
    if not force and db.agents.count_documents({}) > 0:
        return {"seeded": False, "reason": "already_populated", "counts": ping_mongo()["counts"]}

    if not JSON_CACHE_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {JSON_CACHE_PATH}")

    raw = json.loads(JSON_CACHE_PATH.read_text(encoding="utf-8"))
    meta_src = raw.get("meta") or {}
    agents_src = raw.get("agents") or []
    tasks_src = raw.get("tasks") or []
    logs_src = raw.get("activityLog") or []

    if force:
        db.agents.delete_many({})
        db.tasks.delete_many({})
        db.activity_logs.delete_many({})

    for idx, agent in enumerate(agents_src):
        doc = dict(agent)
        doc["_id"] = doc["id"]
        doc["order"] = idx
        doc.setdefault("updatedAt", meta_src.get("updatedAt", now_display()))
        db.agents.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    for idx, task in enumerate(tasks_src):
        doc = dict(task)
        doc["_id"] = doc["id"]
        doc["order"] = idx
        doc.setdefault("createdAt", doc.get("updatedAt", now_display()))
        db.tasks.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    # Logs in JSON are newest-first; assign seq so newest gets highest seq
    total_logs = len(logs_src)
    for idx, log_item in enumerate(logs_src):
        seq = total_logs - idx
        doc = dict(log_item)
        doc["seq"] = seq
        doc.setdefault("createdAt", now_iso())
        db.activity_logs.insert_one(doc)

    db.meta.replace_one(
        {"_id": "singleton"},
        {
            "_id": "singleton",
            "title": meta_src.get("title", "Frank 入口網站 — Agent 工作儀表板"),
            "subtitle": meta_src.get("subtitle", ""),
            "portalUrl": meta_src.get("portalUrl", "https://43-133-44-216.sslip.io"),
            "repoPath": meta_src.get("repoPath", r"F:\github\finlab-stock-analyzer"),
            "updatedAt": meta_src.get("updatedAt", now_display()),
            "revision": 1,
            "lastEvent": {
                "revision": 1,
                "kind": "seed",
                "title": "初始化完成",
                "message": f"已匯入 {len(agents_src)} 位成員與 {len(tasks_src)} 項工作至本機 MongoDB",
                "at": now_display(),
            },
        },
        upsert=True,
    )
    return {
        "seeded": True,
        "agents": len(agents_src),
        "tasks": len(tasks_src),
        "logs": total_logs,
    }


def get_meta_brief() -> dict[str, Any]:
    db = get_db()
    meta = db.meta.find_one({"_id": "singleton"}, {"_id": 0})
    if not meta:
        return {"revision": 0, "updatedAt": "—", "lastEvent": None}
    return meta


def get_state(auto_seed: bool = True) -> dict[str, Any]:
    db = get_db()
    if auto_seed and db.agents.count_documents({}) == 0 and JSON_CACHE_PATH.exists():
        seed_from_json(force=False)

    meta = db.meta.find_one({"_id": "singleton"}, {"_id": 0}) or {
        "title": "Frank 入口網站 — Agent 工作儀表板",
        "subtitle": "",
        "updatedAt": now_display(),
        "revision": 0,
    }
    agents = list(db.agents.find({}, {"_id": 0, "order": 0}).sort("order", ASCENDING))
    tasks = list(
        db.tasks.find({}, {"_id": 0, "order": 0, "report": 0}).sort(
            [("updatedAt", DESCENDING), ("order", ASCENDING)]
        )
    )
    for t in tasks:
        if not t.get("hasReport"):
            t["hasReport"] = (REPORTS_DIR / f"{t.get('id', '')}.md").exists()
    logs = list(
        db.activity_logs.find({}, {"_id": 0, "seq": 0})
        .sort("seq", DESCENDING)
        .limit(80)
    )
    return {
        "meta": meta,
        "agents": agents,
        "tasks": tasks,
        "activityLog": logs,
    }


def export_local_cache() -> dict[str, Any]:
    """Write MongoDB state back to dashboard-data.json and dashboard-data.js as offline fallback."""
    if NO_FILE_CACHE:
        meta = get_meta_brief()
        return {"skipped": True, "revision": int(meta.get("revision", 0))}
    state = get_state(auto_seed=False)
    json_text = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    JSON_CACHE_PATH.write_text(json_text, encoding="utf-8")
    js_text = (
        "// Auto-generated from local MongoDB (agent_dashboard) — do not edit directly.\n"
        f"window.AGENT_DASHBOARD_DATA = {json_text.strip()};\n"
    )
    JS_CACHE_PATH.write_text(js_text, encoding="utf-8")
    return {"json": str(JSON_CACHE_PATH), "js": str(JS_CACHE_PATH), "revision": state["meta"].get("revision", 0)}


def export_full_snapshot() -> dict[str, Any]:
    """Export complete MongoDB collections (including all embedded reports) for cloud migration."""
    db = get_db()
    return {
        "meta": db.meta.find_one({"_id": "singleton"}, {"_id": 0}) or {},
        "agents": list(db.agents.find({}, {"_id": 0}).sort("order", ASCENDING)),
        "tasks": list(db.tasks.find({}, {"_id": 0}).sort("order", ASCENDING)),
        "activity_logs": list(db.activity_logs.find({}, {"_id": 0}).sort("seq", ASCENDING)),
    }


def import_full_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Atomically replace cloud MongoDB collections from a full PC snapshot."""
    ensure_indexes()
    db = get_db()
    agents = snapshot.get("agents") or []
    tasks = snapshot.get("tasks") or []
    logs = snapshot.get("activity_logs") or []
    meta = dict(snapshot.get("meta") or {})
    meta["_id"] = "singleton"
    meta["updatedAt"] = now_display()
    meta["revision"] = int(meta.get("revision", 1)) + 1

    db.agents.delete_many({})
    for idx, doc in enumerate(agents):
        item = dict(doc)
        item["_id"] = item["id"]
        item.setdefault("order", idx)
        db.agents.replace_one({"_id": item["_id"]}, item, upsert=True)

    db.tasks.delete_many({})
    for idx, doc in enumerate(tasks):
        item = dict(doc)
        item["_id"] = item["id"]
        item.setdefault("order", idx)
        db.tasks.replace_one({"_id": item["_id"]}, item, upsert=True)

    db.activity_logs.delete_many({})
    for idx, doc in enumerate(logs):
        item = dict(doc)
        item.setdefault("seq", idx + 1)
        db.activity_logs.insert_one(item)

    db.meta.replace_one({"_id": "singleton"}, meta, upsert=True)
    return {
        "imported": True,
        "agents": len(agents),
        "tasks": len(tasks),
        "logs": len(logs),
        "revision": meta["revision"],
    }


def _agent_name(db, agent_id: str) -> str:
    doc = db.agents.find_one({"_id": agent_id}, {"name": 1})
    return str(doc["name"]) if doc and "name" in doc else agent_id


def add_task(
    *,
    title: str,
    agent_id: str = "foreman",
    description: str = "",
    status: str = "todo",
    priority: str = "P1",
    site: str = "全局",
    branch: str = "待開 worktree",
    tags: Optional[list[str]] = None,
    task_id: Optional[str] = None,
    dispatch: str = "manual",
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    if status not in VALID_TASK_STATUSES:
        raise ValueError(f"Invalid task status: {status}")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}")
    if dispatch not in VALID_DISPATCH_STATES:
        raise ValueError(f"Invalid dispatch state: {dispatch}")

    ensure_indexes()
    db = get_db()
    if db.agents.count_documents({}) == 0 and JSON_CACHE_PATH.exists():
        seed_from_json(force=False)

    tid = task_id.strip() if task_id else _next_task_id(db)
    if db.tasks.find_one({"_id": tid}):
        raise ValueError(f"Task {tid} already exists")

    ts = now_display()
    min_order_doc = db.tasks.find_one(sort=[("order", ASCENDING)], projection={"order": 1})
    new_order = (int(min_order_doc["order"]) - 1) if min_order_doc and "order" in min_order_doc else 0

    task_doc = {
        "_id": tid,
        "id": tid,
        "title": title.strip(),
        "description": description.strip(),
        "agentId": agent_id,
        "status": status,
        "priority": priority,
        "site": site.strip() or "全局",
        "branch": branch.strip() or "—",
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "dispatch": dispatch if status == "todo" else "manual",
        "createdAt": ts,
        "updatedAt": ts,
        "order": new_order,
    }
    db.tasks.insert_one(task_doc)

    agent_label = _agent_name(db, agent_id)
    status_zh = STATUS_LABELS.get(status, status)
    dispatch_suffix = "｜🚀 已加入工頭自動派工佇列" if task_doc["dispatch"] == "queued" else ""
    log_msg = f"新增工作 {tid}「{task_doc['title']}」（指派：{agent_label}，狀態：{status_zh}{dispatch_suffix}）"
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": agent_id,
            "taskId": tid,
            "action": "待派工" if task_doc["dispatch"] == "queued" else "新增工作",
            "fromStatus": None,
            "toStatus": status,
            "message": log_msg,
        }
    )

    event = {
        "kind": "task_queued" if task_doc["dispatch"] == "queued" else "task_added",
        "taskId": tid,
        "agentId": agent_id,
        "toStatus": status,
        "dispatch": task_doc["dispatch"],
        "title": f"{'🚀 待派工' if task_doc['dispatch'] == 'queued' else '新增工作'} {tid}（{priority}）",
        "message": f"{agent_label}：{task_doc['title']}",
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(f"📋 {event['title']}", event["message"])

    clean_task = {k: v for k, v in task_doc.items() if k not in ("_id", "order")}
    return {"task": clean_task, "revision": rev, "event": event}


def update_task(
    task_id: str,
    *,
    status: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    agent_id: Optional[str] = None,
    priority: Optional[str] = None,
    site: Optional[str] = None,
    branch: Optional[str] = None,
    tags: Optional[list[str]] = None,
    dispatch: Optional[str] = None,
    note: Optional[str] = None,
    agent_status: Optional[str] = None,
    agent_text: Optional[str] = None,
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    ensure_indexes()
    db = get_db()
    existing = db.tasks.find_one({"_id": task_id})
    if not existing:
        raise KeyError(f"Task not found: {task_id}")

    updates: dict[str, Any] = {}
    if status is not None:
        if status not in VALID_TASK_STATUSES:
            raise ValueError(f"Invalid task status: {status}")
        updates["status"] = status
        if status == "done" and dispatch is None:
            updates["dispatch"] = "manual"
    if title is not None:
        updates["title"] = title.strip()
    if description is not None:
        updates["description"] = description.strip()
    if agent_id is not None:
        updates["agentId"] = agent_id
    if priority is not None:
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        updates["priority"] = priority
    if site is not None:
        updates["site"] = site.strip()
    if branch is not None:
        updates["branch"] = branch.strip()
    if tags is not None:
        updates["tags"] = [t.strip() for t in tags if t.strip()]
    if dispatch is not None:
        if dispatch not in VALID_DISPATCH_STATES:
            raise ValueError(f"Invalid dispatch state: {dispatch}")
        updates["dispatch"] = dispatch

    ts = now_display()
    updates["updatedAt"] = ts
    db.tasks.update_one({"_id": task_id}, {"$set": updates})
    updated = db.tasks.find_one({"_id": task_id}, {"_id": 0, "order": 0})

    old_status = existing.get("status")
    new_status = updated.get("status")
    old_dispatch = existing.get("dispatch", "manual")
    new_dispatch = updated.get("dispatch", "manual")
    eff_agent_id = updated.get("agentId", "foreman")
    agent_label = _agent_name(db, eff_agent_id)

    # Optionally update assigned agent status in the same atomic workflow
    if agent_status is not None or agent_text is not None:
        a_upd: dict[str, Any] = {"updatedAt": ts}
        if agent_status is not None:
            if agent_status not in VALID_AGENT_STATUSES:
                raise ValueError(f"Invalid agent status: {agent_status}")
            a_upd["status"] = agent_status
        if agent_text is not None:
            a_upd["statusText"] = agent_text.strip()
        db.agents.update_one({"_id": eff_agent_id}, {"$set": a_upd})

    status_changed = old_status != new_status
    dispatch_changed = old_dispatch != new_dispatch
    if status_changed:
        from_zh = STATUS_LABELS.get(old_status, str(old_status))
        to_zh = STATUS_LABELS.get(new_status, str(new_status))
        action = {
            "in_progress": "開工",
            "blocked": "待核准",
            "done": "完工",
            "todo": "退回待辦",
        }.get(new_status, "狀態變更")
        msg = f"{task_id}「{updated['title']}」：{from_zh} → {to_zh}"
        if note:
            msg += f"（{note.strip()}）"
        event_title = f"[{action}] {task_id} → {to_zh}"
        event_msg = f"{agent_label}：{updated['title']}" + (f"｜{note.strip()}" if note else "")
    elif dispatch_changed:
        if new_dispatch == "queued":
            action = "待派工"
            msg = f"{task_id}「{updated['title']}」已標記為「🚀 等待工頭自動派工」"
            event_title = f"🚀 已排入派工佇列 {task_id}"
            event_msg = f"{agent_label}：{updated['title']}"
        elif new_dispatch == "dispatched":
            action = "工頭接單"
            msg = f"工頭已接單並派發 {task_id}「{updated['title']}」給 {agent_label}"
            event_title = f"🤖 工頭已派工 {task_id}"
            event_msg = f"{agent_label}：{updated['title']}"
        else:
            action = "取消派工"
            msg = f"{task_id}「{updated['title']}」已取消自動派工排隊"
            event_title = f"⏸ 取消派工 {task_id}"
            event_msg = updated["title"]
    else:
        action = "更新"
        msg = note.strip() if note else f"已更新工作 {task_id}「{updated['title']}」內容"
        event_title = f"[更新] {task_id}"
        event_msg = msg

    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": eff_agent_id,
            "taskId": task_id,
            "action": action,
            "fromStatus": old_status,
            "toStatus": new_status,
            "message": msg,
        }
    )

    event = {
        "kind": "task_status" if status_changed else "task_updated",
        "taskId": task_id,
        "agentId": eff_agent_id,
        "fromStatus": old_status,
        "toStatus": new_status,
        "title": event_title,
        "message": event_msg,
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        icon = {"done": "✅", "blocked": "❗", "in_progress": "⚡", "todo": "📌"}.get(new_status, "🔔")
        send_windows_toast(f"{icon} {event_title}", event_msg)

    return {"task": updated, "revision": rev, "event": event}


def delete_task(task_id: str, *, notify: bool = False, sync_cache: bool = True) -> dict[str, Any]:
    ensure_indexes()
    db = get_db()
    existing = db.tasks.find_one({"_id": task_id})
    if not existing:
        raise KeyError(f"Task not found: {task_id}")
    db.tasks.delete_one({"_id": task_id})
    ts = now_display()
    msg = f"移除工作 {task_id}「{existing.get('title', '')}」"
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": existing.get("agentId", "foreman"),
            "taskId": task_id,
            "action": "移除",
            "fromStatus": existing.get("status"),
            "toStatus": None,
            "message": msg,
        }
    )
    event = {
        "kind": "task_deleted",
        "taskId": task_id,
        "agentId": existing.get("agentId", "foreman"),
        "title": f"移除工作 {task_id}",
        "message": existing.get("title", ""),
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev
    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(f"🗑️ {event['title']}", event["message"])
    return {"deleted": task_id, "revision": rev, "event": event}


def update_agent(
    agent_id: str,
    *,
    status: Optional[str] = None,
    status_text: Optional[str] = None,
    worktree: Optional[str] = None,
    note: Optional[str] = None,
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    ensure_indexes()
    db = get_db()
    existing = db.agents.find_one({"_id": agent_id})
    if not existing:
        raise KeyError(f"Agent not found: {agent_id}")

    updates: dict[str, Any] = {}
    if status is not None:
        if status not in VALID_AGENT_STATUSES:
            raise ValueError(f"Invalid agent status: {status}")
        updates["status"] = status
    if status_text is not None:
        updates["statusText"] = status_text.strip()
    if worktree is not None:
        updates["worktree"] = worktree.strip()

    ts = now_display()
    updates["updatedAt"] = ts
    db.agents.update_one({"_id": agent_id}, {"$set": updates})
    updated = db.agents.find_one({"_id": agent_id}, {"_id": 0, "order": 0})

    old_status = existing.get("status")
    new_status = updated.get("status")
    agent_label = updated.get("name", agent_id)
    to_zh = STATUS_LABELS.get(new_status, str(new_status))

    msg = note.strip() if note else f"{agent_label} 狀態更新為「{to_zh}」：{updated.get('statusText', '')}"
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": agent_id,
            "taskId": None,
            "action": "成員狀態",
            "fromStatus": old_status,
            "toStatus": new_status,
            "message": msg,
        }
    )

    event = {
        "kind": "agent_status",
        "agentId": agent_id,
        "fromStatus": old_status,
        "toStatus": new_status,
        "title": f"👤 {agent_label} → {to_zh}",
        "message": updated.get("statusText", "") or msg,
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(event["title"], event["message"])

    return {"agent": updated, "revision": rev, "event": event}


def add_log(
    *,
    agent_id: str,
    action: str,
    message: str,
    task_id: Optional[str] = None,
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    ensure_indexes()
    db = get_db()
    ts = now_display()
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": agent_id,
            "taskId": task_id,
            "action": action.strip(),
            "fromStatus": None,
            "toStatus": None,
            "message": message.strip(),
        }
    )
    agent_label = _agent_name(db, agent_id)
    event = {
        "kind": "log",
        "agentId": agent_id,
        "taskId": task_id,
        "title": f"[{action.strip()}] {agent_label}",
        "message": message.strip(),
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(f"📋 {event['title']}", event["message"])

    return {"revision": rev, "event": event}


def list_queued_tasks() -> list[dict[str, Any]]:
    """Return tasks waiting for foreman pickup: new todo queued tasks OR user-approved blocked tasks."""
    ensure_indexes()
    db = get_db()
    docs = list(
        db.tasks.find(
            {
                "dispatch": "queued",
                "$or": [
                    {"status": "todo"},
                    {"approval": "approved"},
                ],
            },
            {"_id": 0, "order": 0, "report": 0},
        )
    )
    for d in docs:
        d["queueReason"] = "approved_continue" if d.get("approval") == "approved" else "new_dispatch"
    docs.sort(
        key=lambda t: (
            0 if t.get("approval") == "approved" else 1,
            PRIORITY_RANK.get(t.get("priority", "P2"), 9),
            t.get("createdAt", ""),
        )
    )
    return docs


def approve_task(
    task_id: str,
    *,
    note: Optional[str] = None,
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    """User approves a blocked/pending task directly on Dashboard -> queues for foreman execution."""
    ensure_indexes()
    db = get_db()
    existing = db.tasks.find_one({"_id": task_id})
    if not existing:
        raise KeyError(f"Task not found: {task_id}")

    ts = now_display()
    old_status = existing.get("status")
    eff_agent_id = existing.get("agentId", "foreman")
    agent_label = _agent_name(db, eff_agent_id)

    update_fields: dict[str, Any] = {
        "approval": "approved",
        "approvedAt": ts,
        "approvalNote": (note or "").strip(),
        "dispatch": "queued",
        "status": "in_progress",
        "updatedAt": ts,
    }
    db.tasks.update_one({"_id": task_id}, {"$set": update_fields})
    updated = db.tasks.find_one({"_id": task_id}, {"_id": 0, "order": 0, "report": 0})

    msg = f"使用者已於儀表板核准 {task_id}「{updated['title']}」，已排入工頭自動執行佇列"
    if note and note.strip():
        msg += f"（核准備註：{note.strip()}）"
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": eff_agent_id,
            "taskId": task_id,
            "action": "已核准",
            "fromStatus": old_status,
            "toStatus": "in_progress",
            "message": msg,
        }
    )

    event = {
        "kind": "task_approved",
        "taskId": task_id,
        "agentId": eff_agent_id,
        "fromStatus": old_status,
        "toStatus": "in_progress",
        "approval": "approved",
        "dispatch": "queued",
        "title": f"✅ 已核准 {task_id}（等待工頭執行）",
        "message": f"{agent_label}：{updated['title']}" + (f"｜{note.strip()}" if note and note.strip() else ""),
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(event["title"], event["message"])

    return {"approved": True, "task": updated, "revision": rev, "event": event}


def reject_task(
    task_id: str,
    *,
    note: str = "",
    requeue: bool = False,
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    """User requests changes / rejects a blocked task on Dashboard."""
    ensure_indexes()
    db = get_db()
    existing = db.tasks.find_one({"_id": task_id})
    if not existing:
        raise KeyError(f"Task not found: {task_id}")

    ts = now_display()
    old_status = existing.get("status")
    eff_agent_id = existing.get("agentId", "foreman")
    reason = (note or "").strip()
    new_desc = existing.get("description", "")
    if reason:
        new_desc = (new_desc + f"\n[退回修改 {ts}] {reason}").strip()

    update_fields: dict[str, Any] = {
        "approval": "rejected",
        "approvalNote": reason,
        "status": "todo",
        "dispatch": "queued" if requeue else "manual",
        "description": new_desc,
        "updatedAt": ts,
    }
    db.tasks.update_one({"_id": task_id}, {"$set": update_fields})
    updated = db.tasks.find_one({"_id": task_id}, {"_id": 0, "order": 0, "report": 0})

    msg = f"使用者於儀表板退回 {task_id}「{updated['title']}」"
    if reason:
        msg += f"（原因：{reason}）"
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": eff_agent_id,
            "taskId": task_id,
            "action": "退回修改",
            "fromStatus": old_status,
            "toStatus": "todo",
            "message": msg,
        }
    )

    event = {
        "kind": "task_rejected",
        "taskId": task_id,
        "agentId": eff_agent_id,
        "fromStatus": old_status,
        "toStatus": "todo",
        "approval": "rejected",
        "title": f"↩ 退回修改 {task_id}",
        "message": reason or updated["title"],
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(event["title"], event["message"])

    return {"rejected": True, "task": updated, "revision": rev, "event": event}


def claim_task(
    task_id: str,
    *,
    note: Optional[str] = None,
    notify: bool = True,
    sync_cache: bool = True,
) -> dict[str, Any]:
    """Atomically claim a queued task (new todo OR user-approved task) and mark agent working."""
    ensure_indexes()
    db = get_db()
    ts = now_display()
    existing = db.tasks.find_one({"_id": task_id, "dispatch": "queued"})
    if not existing:
        return {"claimed": False, "taskId": task_id, "reason": "not_queued_or_already_claimed"}

    was_approved = existing.get("approval") == "approved"
    set_fields: dict[str, Any] = {
        "dispatch": "dispatched",
        "status": "in_progress",
        "updatedAt": ts,
    }
    if was_approved:
        set_fields["approval"] = "executing"

    claimed = db.tasks.find_one_and_update(
        {"_id": task_id, "dispatch": "queued"},
        {"$set": set_fields},
        return_document=True,
    )
    if not claimed:
        return {"claimed": False, "taskId": task_id, "reason": "not_queued_or_already_claimed"}

    eff_agent_id = claimed.get("agentId", "foreman")
    agent_label = _agent_name(db, eff_agent_id)
    short_title = claimed.get("title", "")[:24]
    db.agents.update_one(
        {"_id": eff_agent_id},
        {"$set": {"status": "working", "statusText": f"{'核准執行' if was_approved else '執行'} {task_id}：{short_title}", "updatedAt": ts}},
    )

    action_label = "核准執行" if was_approved else "自動派工"
    msg = (
        f"工頭已接收核准指令，開始執行 {task_id}「{claimed.get('title', '')}」"
        if was_approved
        else f"工頭自動巡檢已接單並派發 {task_id}「{claimed.get('title', '')}」給 {agent_label}"
    )
    if note:
        msg += f"（{note.strip()}）"
    db.activity_logs.insert_one(
        {
            "seq": _next_log_seq(db),
            "time": now_hhmm(),
            "createdAt": now_iso(),
            "agentId": eff_agent_id,
            "taskId": task_id,
            "action": action_label,
            "fromStatus": existing.get("status", "todo"),
            "toStatus": "in_progress",
            "message": msg,
        }
    )

    event = {
        "kind": "task_claimed",
        "taskId": task_id,
        "agentId": eff_agent_id,
        "fromStatus": existing.get("status", "todo"),
        "toStatus": "in_progress",
        "dispatch": "dispatched",
        "approval": claimed.get("approval"),
        "title": f"{'🚀 執行已核准工作' if was_approved else '🤖 工頭自動派工'} {task_id}",
        "message": f"{agent_label}：{claimed.get('title', '')}",
        "at": ts,
    }
    rev = _bump_meta(db, event)
    event["revision"] = rev

    if sync_cache:
        export_local_cache()
    if notify:
        send_windows_toast(event["title"], event["message"])

    clean = {k: v for k, v in claimed.items() if k not in ("_id", "order", "report")}
    return {"claimed": True, "wasApproved": was_approved, "task": clean, "revision": rev, "event": event}


def save_task_report(task_id: str, markdown: str, *, sync_cache: bool = True) -> dict[str, Any]:
    """Persist full task inspection/delivery report into both MongoDB (tasks.report) and reports/<id>.md."""
    ensure_indexes()
    db = get_db()
    existing = db.tasks.find_one({"_id": task_id})
    if not existing:
        raise KeyError(f"Task not found: {task_id}")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{task_id}.md"
    report_path.write_text(markdown, encoding="utf-8")
    ts = now_display()
    db.tasks.update_one(
        {"_id": task_id},
        {"$set": {"report": markdown, "hasReport": True, "reportUpdatedAt": ts}},
    )
    rev = _bump_meta(db)
    if sync_cache:
        export_local_cache()
    return {"taskId": task_id, "filePath": str(report_path), "revision": rev}


def get_task_report(task_id: str) -> dict[str, Any]:
    db = get_db()
    doc = db.tasks.find_one({"_id": task_id}, {"_id": 0, "id": 1, "title": 1, "report": 1, "reportUpdatedAt": 1})
    report_path = REPORTS_DIR / f"{task_id}.md"
    md = (doc or {}).get("report")
    if not md and report_path.exists():
        md = report_path.read_text(encoding="utf-8")
    if not md:
        raise KeyError(f"Report not found for {task_id}")
    return {
        "taskId": task_id,
        "title": (doc or {}).get("title", task_id),
        "markdown": md,
        "filePath": str(report_path) if report_path.exists() else "",
        "updatedAt": (doc or {}).get("reportUpdatedAt", ""),
    }
