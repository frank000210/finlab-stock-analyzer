from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pymongo.database import Database

from knowledge_base.documents import upsert_versioned, utc_now_iso


KEYWORD_TAGS = {
    "mongodb": "mongodb",
    "obsidian": "obsidian",
    "workflow": "workflow",
    "todo": "todo-management",
    "待辦": "todo-management",
    "流程": "workflow",
    "知識庫": "knowledge-base",
    "knowledge": "knowledge-base",
    "sync": "sync",
    "同步": "sync",
    "decision": "decision",
    "決策": "decision",
    "盲點": "blindspot",
    "風險": "risk",
    "創新": "innovation",
    "提議": "innovation",
    "架構": "architecture",
    "規劃": "planning",
    "roadmap": "planning",
}

DECISION_SIGNALS = ["決策", "決定", "採用", "方案", "核准", "確認", "approve", "decision", "選擇"]
INNOVATION_SIGNALS = ["創新", "提議", "優化", "改善", "roadmap", "演進", "strategy", "策略"]
BLINDSPOT_SIGNAL_MAP = {
    "risk_control": ["風險", "risk", "rollback"],
    "clarity": ["不清楚", "釐清", "clarify", "assumption", "假設", "前提"],
    "scope_control": ["scope", "範圍", "擴張", "過度工程"],
}


@dataclass
class SessionLog:
    session_id: str
    file_path: str
    start_time: str = ""
    prompts: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    cwd: str = ""

    def add_prompt(self, prompt: str) -> None:
        prompt = prompt.strip()
        if prompt:
            self.prompts.append(prompt)

    def add_assistant_message(self, message: str) -> None:
        message = message.strip()
        if message:
            self.assistant_messages.append(message)


def _clip(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _contains_any(text: str, signals: list[str]) -> bool:
    lowered = text.lower()
    return any(s.lower() in lowered for s in signals)


def _extract_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = sorted({tag for keyword, tag in KEYWORD_TAGS.items() if keyword.lower() in lowered})
    return tags


def _session_topic(prompt_text: str) -> str:
    first_line = prompt_text.splitlines()[0].strip() if prompt_text.strip() else "Session insight"
    return _clip(first_line, 80)


def _parse_event_file(path: Path) -> SessionLog | None:
    session_data: SessionLog | None = None
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = str(event.get("type", ""))
            data = event.get("data", {})

            if event_type == "session.start":
                session_id = str(data.get("sessionId", "")).strip()
                if not session_id:
                    continue
                session_data = SessionLog(
                    session_id=session_id,
                    file_path=str(path),
                    start_time=str(data.get("startTime", "")),
                    cwd=str(data.get("context", {}).get("cwd", "")),
                )
                continue

            if session_data is None:
                continue

            if event_type == "hook.start" and str(data.get("hookType", "")) == "userPromptSubmitted":
                prompt = str(data.get("input", {}).get("prompt", ""))
                session_data.add_prompt(prompt)
                continue

            if event_type == "assistant.message":
                content = str(data.get("content", ""))
                session_data.add_assistant_message(content)

    return session_data


def _extract_global_preferences(prompts: list[str]) -> dict[str, Any]:
    counters = Counter()
    for prompt in prompts:
        if _contains_any(prompt, ["待核准", "核准", "確認後", "review"]):
            counters["approval_gate"] += 1
        if _contains_any(prompt, ["不清楚", "請提問", "先確認", "clarify"]):
            counters["clarification_first"] += 1
        if _contains_any(prompt, ["先提供大綱", "先提出規劃", "outline"]):
            counters["outline_first"] += 1
        if _contains_any(prompt, ["盲點", "風險", "風險提醒"]):
            counters["risk_alert_preferred"] += 1
    return {
        "approval_gate_preference": counters["approval_gate"],
        "clarification_first_preference": counters["clarification_first"],
        "outline_first_preference": counters["outline_first"],
        "risk_alert_preference": counters["risk_alert_preferred"],
    }


def ingest_event_logs(
    db: Database,
    root_path: Path,
    profile_key: str = "owner-default",
    include_session_ids: set[str] | None = None,
) -> dict[str, int]:
    event_paths = sorted(root_path.glob("**/events.jsonl"))
    sessions: list[SessionLog] = []
    for path in event_paths:
        parsed = _parse_event_file(path)
        if parsed is None:
            continue
        if include_session_ids is not None and parsed.session_id not in include_session_ids:
            continue
        if parsed.prompts or parsed.assistant_messages:
            sessions.append(parsed)

    total_domain = 0
    total_decision = 0
    total_innovation = 0
    total_blindspot = 0
    total_workflow_runs = 0
    all_prompts: list[str] = []

    for session in sessions:
        prompts_text = "\n\n".join(session.prompts)
        assistant_text = "\n\n".join(session.assistant_messages)
        combined_text = f"{prompts_text}\n\n{assistant_text}".strip()
        tags = _extract_tags(combined_text)
        all_prompts.extend(session.prompts)

        db["sessions_raw"].update_one(
            {"session_id": session.session_id},
            {
                "$set": {
                    "session_id": session.session_id,
                    "source_file": session.file_path,
                    "start_time": session.start_time,
                    "cwd": session.cwd,
                    "prompt_count": len(session.prompts),
                    "assistant_message_count": len(session.assistant_messages),
                    "prompt_excerpt": _clip(prompts_text, 4000),
                    "assistant_excerpt": _clip(assistant_text, 4000),
                    "tags": tags,
                    "ingested_at": utc_now_iso(),
                }
            },
            upsert=True,
        )

        topic = _session_topic(prompts_text)
        slug = f"session-{session.session_id[:8]}-insight"
        upsert_versioned(
            db,
            "domain_pages",
            "slug",
            slug,
            {
                "title": f"Session insight {session.session_id[:8]}",
                "summary": topic,
                "content": (
                    "### User prompts\n\n"
                    f"{_clip(prompts_text, 5000) or '(none)'}\n\n"
                    "### Assistant outputs\n\n"
                    f"{_clip(assistant_text, 5000) or '(none)'}"
                ),
                "tags": sorted(set(tags + ["session-log"])),
                "related_slugs": [],
                "last_source_session": session.session_id,
                "knowledge_scope": "session",
            },
        )
        total_domain += 1

        run_id = f"session-{session.session_id[:8]}-workflow"
        upsert_versioned(
            db,
            "workflow_runs",
            "run_id",
            run_id,
            {
                "session_id": session.session_id,
                "date": session.start_time[:10] if session.start_time else utc_now_iso()[:10],
                "title": topic,
                "status": "done",
                "plan": _clip(prompts_text, 1500),
                "actual": _clip(assistant_text, 1500),
                "deviation": "",
                "improvement": "",
                "workflow_slug": "session-log-ingest",
                "tags": sorted(set(tags + ["session-log"])),
                "knowledge_scope": "session",
            },
        )
        total_workflow_runs += 1

        if _contains_any(combined_text, DECISION_SIGNALS):
            decision_id = f"session-{session.session_id[:8]}-decision"
            upsert_versioned(
                db,
                "decision_logs",
                "decision_id",
                decision_id,
                {
                    "session_id": session.session_id,
                    "title": f"Decision trace from session {session.session_id[:8]}",
                    "summary": topic,
                    "reasoning": _clip(combined_text, 3000),
                    "tradeoffs": [],
                    "rejected_options": [],
                    "tags": sorted(set(tags + ["session-log"])),
                    "outcome": "",
                    "knowledge_scope": "session",
                },
            )
            total_decision += 1

        if _contains_any(combined_text, INNOVATION_SIGNALS):
            innovation_id = f"session-{session.session_id[:8]}-innovation"
            upsert_versioned(
                db,
                "innovation_logs",
                "innovation_id",
                innovation_id,
                {
                    "session_id": session.session_id,
                    "title": f"Innovation trace from session {session.session_id[:8]}",
                    "hypothesis": topic,
                    "validation_plan": "Review follow-up sessions for measurable outcome.",
                    "result": "",
                    "tags": sorted(set(tags + ["session-log"])),
                    "knowledge_scope": "session",
                },
            )
            total_innovation += 1

        lowered = combined_text.lower()
        for category, terms in BLINDSPOT_SIGNAL_MAP.items():
            if any(term.lower() in lowered for term in terms):
                alert_id = f"session-{session.session_id[:8]}-{category}"
                upsert_versioned(
                    db,
                    "blindspot_alerts",
                    "alert_id",
                    alert_id,
                    {
                        "session_id": session.session_id,
                        "title": f"{category} alert from session {session.session_id[:8]}",
                        "category": category,
                        "trigger_rule": f"Detected keywords: {', '.join(terms)}",
                        "recommended_action": "Review the related session insight page before next execution.",
                        "status": "active",
                        "tags": sorted(set(tags + ["session-log"])),
                        "knowledge_scope": "session",
                    },
                )
                total_blindspot += 1

    # Keep one shared playbook for this ingestion path.
    upsert_versioned(
        db,
        "workflow_playbooks",
        "slug",
        "session-log-ingest",
        {
            "title": "Session Log Ingestion Flow",
            "summary": "Extract prompts/outputs from events.jsonl and compile into reusable knowledge.",
            "steps": ["Read logs", "Extract prompts", "Compile knowledge pages", "Sync vault"],
            "done_definition": "All session logs converted into domain/workflow records.",
            "risks": ["Noisy prompts", "Overly broad tags"],
            "tags": ["automation", "knowledge-base"],
            "knowledge_scope": "session",
        },
    )

    profile_payload = _extract_global_preferences(all_prompts)
    upsert_versioned(
        db,
        "decision_profiles",
        "profile_key",
        profile_key,
        {
            "preferences": profile_payload,
            "notes": "Auto-derived from historical session prompts.",
            "last_source_session": sessions[-1].session_id if sessions else "",
            "knowledge_scope": "session",
        },
    )

    db["sync_state"].update_one(
        {"key": "last_eventlog_ingest"},
        {
            "$set": {
                "key": "last_eventlog_ingest",
                "value": utc_now_iso(),
                "eventlog_root": str(root_path),
                "session_count": len(sessions),
                "updated_at": utc_now_iso(),
            }
        },
        upsert=True,
    )

    return {
        "sessions": len(sessions),
        "domain_pages": total_domain,
        "workflow_runs": total_workflow_runs,
        "decisions": total_decision,
        "innovations": total_innovation,
        "blindspots": total_blindspot,
    }
