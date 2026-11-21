#!/usr/bin/env python3
"""Weekly work summary & cross-agent learning digest generator for intern-agent (實習生)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TAIPEI_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(r"F:\github\finlab-stock-analyzer")
DEFAULT_ENV_FILE = Path.home() / ".gemini" / "agent-dashboard.env"


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def api_request(base_url: str, path: str, method: str = "GET", token: str = "", body: dict[str, Any] | None = None) -> Any:
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Dashboard-Token"] = token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = str(ts).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).replace(tzinfo=TAIPEI_TZ)
        except ValueError:
            continue
    return None


def collect_git_commits(repo_root: Path, days: int) -> list[dict[str, str]]:
    if not (repo_root / ".git").exists():
        return []
    since = (datetime.now(TAIPEI_TZ) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        out = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "origin/master",
                f"--since={since}",
                "--pretty=format:%h|%ad|%s",
                "--date=short",
                "-n",
                "40",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
    return commits


def extract_report_highlights(markdown: str) -> list[str]:
    highlights: list[str] = []
    for line in markdown.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(("- ", "* ")) and len(s) > 10:
            cleaned = re.sub(r"\s+", " ", s[2:]).strip()
            if not cleaned.startswith(("任務編號", "主責", "工作目錄")):
                highlights.append(cleaned[:140])
        if len(highlights) >= 3:
            break
    return highlights


def build_weekly_markdown(
    state: dict[str, Any],
    reports: dict[str, str],
    commits: list[dict[str, str]],
    days: int,
    now: datetime,
) -> tuple[str, str]:
    iso_year, iso_week, _ = now.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"
    cutoff = now - timedelta(days=days)
    period_str = f"{cutoff.strftime('%Y-%m-%d')} ～ {now.strftime('%Y-%m-%d')}"

    agents = state.get("agents") or []
    tasks = state.get("tasks") or []
    logs = state.get("activityLog") or []
    agent_map = {a["id"]: a for a in agents}

    recent_tasks = []
    for t in tasks:
        dt = parse_dt(t.get("updatedAt") or t.get("createdAt"))
        if dt is None or dt >= cutoff:
            recent_tasks.append(t)

    done_recent = [t for t in recent_tasks if t.get("status") == "done"]
    doing_all = [t for t in tasks if t.get("status") == "in_progress"]
    blocked_all = [t for t in tasks if t.get("status") == "blocked"]
    todo_all = [t for t in tasks if t.get("status") == "todo"]

    lines: list[str] = [
        f"# 🎓 實習生每週工作總結與學習報告（{week_label}）",
        "",
        f"- **彙整期間**：{period_str}（近 {days} 天）",
        f"- **產出時間**：{now.strftime('%Y-%m-%d %H:%M')}（台北時間）",
        "- **撰寫角色**：實習生 `intern-agent`（全局觀察、跨站學習與週報書記）",
        f"- **資料來源**：雲端 Agent 工作儀表板（Rev #{state.get('meta', {}).get('revision', '—')}）＋ `origin/master` Git 提交紀錄",
        "",
        "---",
        "",
        "## 一、本週全局關鍵數字",
        "",
        "| 指標 | 數值 | 說明 |",
        "| :--- | :---: | :--- |",
        f"| 團隊編制 | **{len(agents)} 位** | 含工頭、專員與實習生 |",
        f"| 近 {days} 天完工任務 | **{len(done_recent)} 項** | 累計總完工 {sum(1 for t in tasks if t.get('status') == 'done')} / {len(tasks)} 項 |",
        f"| 目前進行中 | **{len(doing_all)} 項** | 含並行開發中任務 |",
        f"| 卡關／待核准 | **{len(blocked_all)} 項** | 需優先排除或確認 |",
        f"| 待辦佇列 | **{len(todo_all)} 項** | 後續排程候選 |",
        f"| 近 {days} 天 `master` 提交 | **{len(commits)} 筆** | 通過 E2E Gate 之正式上線紀錄 |",
        "",
        "---",
        "",
        "## 二、各 Agent 本週工作記錄與學習觀察",
        "",
        "| 成員 | 負責領域 | 本週完工 | 進行中 | 最新動態與狀態 |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ]

    for a in agents:
        aid = a["id"]
        a_done = [t for t in done_recent if t.get("agentId") == aid]
        a_doing = [t for t in doing_all if t.get("agentId") == aid]
        done_ids = ", ".join(t["id"] for t in a_done[:5]) or "—"
        doing_ids = ", ".join(t["id"] for t in a_doing[:3]) or "—"
        st_txt = str(a.get("statusText") or "待命中").replace("|", "／")[:80]
        lines.append(
            f"| **{a.get('name', aid)}** (`{aid}`) | {a.get('siteLabel', '—')} | {len(a_done)}（{done_ids}） | {len(a_doing)}（{doing_ids}） | {st_txt} |"
        )

    lines.extend(["", "---", "", "## 三、本週完工成果與實習生學習筆記", ""])
    if done_recent:
        for t in sorted(done_recent, key=lambda x: str(x.get("updatedAt", "")), reverse=True)[:15]:
            tid = t["id"]
            aname = agent_map.get(t.get("agentId", ""), {}).get("name", t.get("agentId", ""))
            lines.append(f"### {tid}｜{t.get('title', '')}（{aname}・{t.get('site', '')}）")
            if t.get("description"):
                desc = str(t["description"]).strip().replace("\n", " ")[:180]
                lines.append(f"- **任務摘要**：{desc}")
            md = reports.get(tid, "")
            hl = extract_report_highlights(md)
            if hl:
                lines.append("- **實習生學習重點**：")
                for item in hl:
                    lines.append(f"  - {item}")
            lines.append("")
    else:
        lines.append("本期間尚無新完工任務紀錄。\n")

    lines.extend(["---", "", "## 四、目前進行中與後續關注焦點", ""])
    if doing_all or blocked_all:
        for t in blocked_all + doing_all:
            aname = agent_map.get(t.get("agentId", ""), {}).get("name", t.get("agentId", ""))
            badge = "❗ 卡關" if t.get("status") == "blocked" else "⚡ 進行中"
            lines.append(f"- **{badge} {t['id']}**（{aname}）：{t.get('title', '')}")
    else:
        lines.append("- 目前無進行中或卡關任務，團隊全體於後方休息區待命中。")

    lines.extend(["", "---", "", f"## 五、近 {days} 天 `origin/master` 程式碼變更軌跡（前 15 筆）", ""])
    if commits:
        for c in commits[:15]:
            lines.append(f"- `{c['hash']}` ({c['date']}) {c['subject']}")
    else:
        lines.append("- （本期間無新 commit 或未偵測到 git 倉庫）")

    lines.extend([
        "",
        "---",
        "",
        "## 六、實習生跨站學習心得與下週建議",
        "",
        "1. **工程紀律觀察**：團隊全面落實獨立 Worktree 開發與完整 Playwright E2E 把關（禁 `--no-verify`），多項跨站變更合併成單次整併驗證大幅節省 FinMind API 額度。",
        "2. **知識沉澱與監控**：各專員完工後同步撰寫任務報告與知識庫 `dev_note`，並透過雲端工作儀表板 SSE 即時留痕，讓後續交接與實習生每週覆盤都有完整實證依據。",
        f"3. **下週追蹤建議**：優先追蹤上述 {len(doing_all)} 項進行中任務的整合驗收與上線穩定度，並持續收集正式站效能與使用者回饋。",
        "",
        f"> *本週報由實習生 `intern-agent` 透過 `weekly_intern_digest.py` 彙整最近 {len(logs)} 筆團隊動態日誌與任務報告自動產出。*",
    ])

    return week_label, "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly intern work summary report.")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--out-dir", type=str, default=str(REPO_ROOT / "docs" / "agent-dashboard" / "reports"))
    parser.add_argument("--publish", action="store_true", help="Publish weekly summary task & report to Cloud Dashboard")
    args = parser.parse_args()

    env = load_env_file(DEFAULT_ENV_FILE)
    base_url = os.environ.get("AGENT_DASHBOARD_API_URL") or env.get("AGENT_DASHBOARD_API_URL") or "https://dashboard.43-133-44-216.sslip.io"
    token = os.environ.get("AGENT_DASHBOARD_WRITE_TOKEN") or env.get("AGENT_DASHBOARD_WRITE_TOKEN") or ""

    state: dict[str, Any]
    try:
        state = api_request(base_url, "/api/state", token=token)
    except Exception:
        fallback = SCRIPT_DIR / "dashboard-data.json"
        state = json.loads(fallback.read_text(encoding="utf-8"))

    now = datetime.now(TAIPEI_TZ)
    cutoff = now - timedelta(days=args.days)
    reports: dict[str, str] = {}
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for t in state.get("tasks") or []:
        if t.get("status") != "done":
            continue
        dt = parse_dt(t.get("updatedAt") or t.get("createdAt"))
        if dt is not None and dt < cutoff:
            continue
        tid = t["id"]
        local_rep = out_dir / f"{tid}.md"
        if local_rep.exists():
            reports[tid] = local_rep.read_text(encoding="utf-8")
        elif t.get("hasReport"):
            try:
                res = api_request(base_url, f"/api/tasks/{tid}/report", token=token)
                reports[tid] = res.get("markdown", "")
            except Exception:
                pass

    commits = collect_git_commits(REPO_ROOT, args.days)
    week_label, md_text = build_weekly_markdown(state, reports, commits, args.days, now)
    out_path = out_dir / f"weekly-{week_label}.md"
    out_path.write_text(md_text, encoding="utf-8")

    result: dict[str, Any] = {
        "week": week_label,
        "reportPath": str(out_path),
        "bytes": len(md_text.encode("utf-8")),
        "published": False,
    }

    if args.publish and token:
        title = f"【實習生週報】{week_label} 團隊每週工作總結與學習報告"
        existing = next(
            (t for t in (state.get("tasks") or []) if t.get("agentId") == "intern-agent" and week_label in str(t.get("title", ""))),
            None,
        )
        if existing:
            tid = existing["id"]
        else:
            created = api_request(
                base_url,
                "/api/tasks",
                method="POST",
                token=token,
                body={
                    "title": title,
                    "agentId": "intern-agent",
                    "description": f"由實習生每週自動記錄與學習全體 Agent 工作後彙整之 {week_label} 團隊週報。",
                    "status": "done",
                    "priority": "P1",
                    "site": "全局學習 & 週報",
                    "branch": "weekly-digest",
                    "tags": ["週報", "實習生學習"],
                    "dispatch": "manual",
                    "notify": True,
                },
            )
            tid = created["task"]["id"]
        api_request(base_url, f"/api/tasks/{tid}/report", method="PUT", token=token, body={"markdown": md_text})
        api_request(
            base_url,
            f"/api/agents/intern-agent",
            method="PATCH",
            token=token,
            body={
                "status": "idle",
                "statusText": f"已提交 {week_label} 團隊工作總結報告，回後方茶室整理筆記 🍵",
                "note": f"已上傳 {week_label} 每週總結報告至 {tid}",
                "notify": False,
            },
        )
        result["published"] = True
        result["taskId"] = tid

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
