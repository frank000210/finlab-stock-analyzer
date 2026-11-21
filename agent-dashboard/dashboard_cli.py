"""CLI for syncing Agent Work Dashboard tasks/agents (supports Cloud HTTPS API or Local MongoDB)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

import db_store

ENV_CANDIDATES = [
    Path(__file__).resolve().parent / ".env.cloud",
    Path.home() / ".gemini" / "agent-dashboard.env",
]


def _load_cloud_env() -> tuple[str, str]:
    url = os.environ.get("AGENT_DASHBOARD_REMOTE_URL", "").strip().rstrip("/")
    tok = os.environ.get("AGENT_DASHBOARD_WRITE_TOKEN", "").strip()
    if url:
        return url, tok
    for p in ENV_CANDIDATES:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == "AGENT_DASHBOARD_REMOTE_URL" and not url:
                url = v.rstrip("/")
            elif k == "AGENT_DASHBOARD_WRITE_TOKEN" and not tok:
                tok = v
        if url:
            break
    return url, tok


def _remote_call(base_url: str, token: str, method: str, path: str, body: Optional[dict[str, Any]] = None) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Dashboard-Token"] = token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{base_url}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _maybe_toast(enabled: bool, event: Optional[dict[str, Any]]) -> None:
    if not enabled or not event or os.name != "nt":
        return
    db_store.send_windows_toast(event.get("title", "Agent 工作儀表板"), event.get("message", ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent Work Dashboard CLI (Cloud HTTPS API / Local MongoDB)"
    )
    parser.add_argument("--local", action="store_true", help="強制操作本機 MongoDB，忽略雲端設定")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="從 dashboard-data.json 匯入初始資料")
    p_seed.add_argument("--force", action="store_true")

    sub.add_parser("status", help="檢視資料庫連線與各狀態統計")
    sub.add_parser("export-cache", help="將資料匯出至本地離線快取")
    sub.add_parser("export-snapshot", help="匯出完整 MongoDB 快照（含所有報告）供遷移上雲")

    p_imp = sub.add_parser("import-snapshot", help="將完整快照匯入雲端或本機 MongoDB")
    p_imp.add_argument("--file", required=True, help="快照 JSON 檔路徑")

    p_rep = sub.add_parser("report-save", help="將任務 Markdown 報告寫入雲端／本機 MongoDB")
    p_rep.add_argument("--id", required=True, help="工作編號，例如 T-021")
    p_rep.add_argument("--file", required=True, help="Markdown 報告檔案路徑")

    p_add = sub.add_parser("task-add", help="新增工作")
    p_add.add_argument("--id", dest="task_id", default=None)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--agent", default="foreman")
    p_add.add_argument("--desc", default="")
    p_add.add_argument("--status", default="todo", choices=sorted(db_store.VALID_TASK_STATUSES))
    p_add.add_argument("--priority", default="P1", choices=sorted(db_store.VALID_PRIORITIES))
    p_add.add_argument("--site", default="全局")
    p_add.add_argument("--branch", default="待開 worktree")
    p_add.add_argument("--tags", default="")
    p_add.add_argument("--dispatch", default="manual", choices=sorted(db_store.VALID_DISPATCH_STATES))
    p_add.add_argument("--no-notify", action="store_true")

    sub.add_parser("queue", help="列出等待工頭自動派工（dispatch=queued）的待辦任務")

    p_claim = sub.add_parser("claim", help="原子接單")
    p_claim.add_argument("--id", required=True)
    p_claim.add_argument("--note", default=None)
    p_claim.add_argument("--no-notify", action="store_true")

    p_approve = sub.add_parser("approve", help="核准待核准工作")
    p_approve.add_argument("--id", required=True)
    p_approve.add_argument("--note", default=None)
    p_approve.add_argument("--no-notify", action="store_true")

    p_reject = sub.add_parser("reject", help="退回待核准工作")
    p_reject.add_argument("--id", required=True)
    p_reject.add_argument("--note", default="")
    p_reject.add_argument("--requeue", action="store_true")
    p_reject.add_argument("--no-notify", action="store_true")

    p_tstat = sub.add_parser("task-status", help="更新工作狀態")
    p_tstat.add_argument("--id", required=True)
    p_tstat.add_argument("--status", required=True, choices=sorted(db_store.VALID_TASK_STATUSES))
    p_tstat.add_argument("--note", default=None)
    p_tstat.add_argument("--agent", default=None)
    p_tstat.add_argument("--agent-status", default=None, choices=sorted(db_store.VALID_AGENT_STATUSES))
    p_tstat.add_argument("--agent-text", default=None)
    p_tstat.add_argument("--no-notify", action="store_true")

    p_tdel = sub.add_parser("task-delete", help="刪除指定工作")
    p_tdel.add_argument("--id", required=True)

    p_astat = sub.add_parser("agent-status", help="更新 Agent 即時狀態")
    p_astat.add_argument("--id", required=True)
    p_astat.add_argument("--status", default=None, choices=sorted(db_store.VALID_AGENT_STATUSES))
    p_astat.add_argument("--text", default=None)
    p_astat.add_argument("--worktree", default=None)
    p_astat.add_argument("--note", default=None)
    p_astat.add_argument("--no-notify", action="store_true")

    p_log = sub.add_parser("log", help="新增一筆工頭派工日誌")
    p_log.add_argument("--agent", default="foreman")
    p_log.add_argument("--action", default="通知")
    p_log.add_argument("--message", required=True)
    p_log.add_argument("--task-id", default=None)
    p_log.add_argument("--no-notify", action="store_true")

    p_tn = sub.add_parser("test-notify", help="測試本機 Windows 桌面通知")
    p_tn.add_argument("--title", default="Agent 工作儀表板測試通知")
    p_tn.add_argument("--message", default="雲端 MongoDB 與桌面通知運作正常！")

    args = parser.parse_args(argv)
    remote_url, write_token = ("", "") if args.local else _load_cloud_env()

    if args.cmd == "test-notify":
        ok = db_store.send_windows_toast(args.title, args.message)
        _print_json({"notified": ok, "title": args.title, "message": args.message})
        return 0

    if args.cmd == "export-snapshot":
        _print_json(db_store.export_full_snapshot())
        return 0

    # --- Cloud Remote HTTPS Mode ---
    if remote_url:
        if args.cmd == "status":
            info = _remote_call(remote_url, write_token, "GET", "/api/health")
            st = _remote_call(remote_url, write_token, "GET", "/api/state")
            by_status: dict[str, int] = {}
            for t in st.get("tasks", []):
                by_status[t["status"]] = by_status.get(t["status"], 0) + 1
            info["tasksByStatus"] = by_status
            info["remoteUrl"] = remote_url
            _print_json(info)
            return 0
        if args.cmd == "queue":
            _print_json(_remote_call(remote_url, write_token, "GET", "/api/dispatch/queue"))
            return 0
        if args.cmd == "claim":
            res = _remote_call(remote_url, write_token, "POST", f"/api/tasks/{urllib.parse.quote(args.id)}/claim", {"note": args.note, "notify": False})
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "approve":
            res = _remote_call(remote_url, write_token, "POST", f"/api/tasks/{urllib.parse.quote(args.id)}/approve", {"note": args.note, "notify": False})
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "reject":
            res = _remote_call(remote_url, write_token, "POST", f"/api/tasks/{urllib.parse.quote(args.id)}/reject", {"note": args.note, "requeue": args.requeue, "notify": False})
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "task-add":
            tags = [x.strip() for x in args.tags.split(",") if x.strip()] if args.tags else []
            res = _remote_call(remote_url, write_token, "POST", "/api/tasks", {
                "title": args.title, "agentId": args.agent, "description": args.desc,
                "status": args.status, "priority": args.priority, "site": args.site,
                "branch": args.branch, "tags": tags, "dispatch": args.dispatch, "notify": False,
            })
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "task-status":
            res = _remote_call(remote_url, write_token, "PATCH", f"/api/tasks/{urllib.parse.quote(args.id)}", {
                "status": args.status, "agentId": args.agent, "note": args.note,
                "agentStatus": args.agent_status, "agentText": args.agent_text, "notify": False,
            })
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "task-delete":
            _print_json(_remote_call(remote_url, write_token, "DELETE", f"/api/tasks/{urllib.parse.quote(args.id)}"))
            return 0
        if args.cmd == "agent-status":
            res = _remote_call(remote_url, write_token, "PATCH", f"/api/agents/{urllib.parse.quote(args.id)}", {
                "status": args.status, "statusText": args.text, "worktree": args.worktree,
                "note": args.note, "notify": False,
            })
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "log":
            res = _remote_call(remote_url, write_token, "POST", "/api/logs", {
                "agentId": args.agent, "action": args.action, "message": args.message,
                "taskId": args.task_id, "notify": False,
            })
            _maybe_toast(not args.no_notify, res.get("event"))
            _print_json(res)
            return 0
        if args.cmd == "report-save":
            md = Path(args.file).read_text(encoding="utf-8")
            _print_json(_remote_call(remote_url, write_token, "PUT", f"/api/tasks/{urllib.parse.quote(args.id)}/report", {"markdown": md}))
            return 0
        if args.cmd == "import-snapshot":
            snap = json.loads(Path(args.file).read_text(encoding="utf-8"))
            _print_json(_remote_call(remote_url, write_token, "POST", "/api/import-snapshot", snap))
            return 0
        if args.cmd == "export-cache":
            st = _remote_call(remote_url, write_token, "GET", "/api/state")
            txt = json.dumps(st, ensure_ascii=False, indent=2) + "\n"
            db_store.JSON_CACHE_PATH.write_text(txt, encoding="utf-8")
            db_store.JS_CACHE_PATH.write_text(f"// Synced from {remote_url}\nwindow.AGENT_DASHBOARD_DATA = {txt.strip()};\n", encoding="utf-8")
            _print_json({"syncedFrom": remote_url, "revision": st.get("meta", {}).get("revision", 0)})
            return 0

    # --- Local MongoDB Fallback Mode ---
    if args.cmd == "seed":
        res = db_store.seed_from_json(force=args.force)
        if res.get("seeded"):
            db_store.export_local_cache()
        _print_json(res)
        return 0
    if args.cmd == "import-snapshot":
        snap = json.loads(Path(args.file).read_text(encoding="utf-8"))
        _print_json(db_store.import_full_snapshot(snap))
        return 0
    if args.cmd == "report-save":
        md = Path(args.file).read_text(encoding="utf-8")
        _print_json(db_store.save_task_report(args.id, md))
        return 0
    if args.cmd == "status":
        info = db_store.ping_mongo()
        st = db_store.get_state(auto_seed=False)
        by_status = {}
        for t in st["tasks"]:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        info["tasksByStatus"] = by_status
        _print_json(info)
        return 0
    if args.cmd == "export-cache":
        _print_json(db_store.export_local_cache())
        return 0
    if args.cmd == "queue":
        tasks = db_store.list_queued_tasks()
        _print_json({"count": len(tasks), "tasks": tasks})
        return 0
    if args.cmd == "claim":
        _print_json(db_store.claim_task(args.id, note=args.note, notify=not args.no_notify))
        return 0
    if args.cmd == "approve":
        _print_json(db_store.approve_task(args.id, note=args.note, notify=not args.no_notify))
        return 0
    if args.cmd == "reject":
        _print_json(db_store.reject_task(args.id, note=args.note, requeue=args.requeue, notify=not args.no_notify))
        return 0
    if args.cmd == "task-add":
        tags = [x.strip() for x in args.tags.split(",") if x.strip()] if args.tags else []
        _print_json(db_store.add_task(
            task_id=args.task_id, title=args.title, agent_id=args.agent, description=args.desc,
            status=args.status, priority=args.priority, site=args.site, branch=args.branch,
            tags=tags, dispatch=args.dispatch, notify=not args.no_notify,
        ))
        return 0
    if args.cmd == "task-status":
        _print_json(db_store.update_task(
            args.id, status=args.status, agent_id=args.agent, note=args.note,
            agent_status=args.agent_status, agent_text=args.agent_text, notify=not args.no_notify,
        ))
        return 0
    if args.cmd == "task-delete":
        _print_json(db_store.delete_task(args.id))
        return 0
    if args.cmd == "agent-status":
        _print_json(db_store.update_agent(
            args.id, status=args.status, status_text=args.text, worktree=args.worktree,
            note=args.note, notify=not args.no_notify,
        ))
        return 0
    if args.cmd == "log":
        _print_json(db_store.add_log(
            agent_id=args.agent, action=args.action, message=args.message,
            task_id=args.task_id, notify=not args.no_notify,
        ))
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
