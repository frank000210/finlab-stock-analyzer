from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pymongo.database import Database

from knowledge_base.documents import refresh_related_links, upsert_versioned, utc_now_iso


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Session file root must be a JSON object.")
    return payload


def ingest_session_file(db: Database, file_path: Path) -> dict[str, int]:
    payload = _read_json(file_path)
    session_id = str(payload.get("session_id", "")).strip()
    if not session_id:
        raise ValueError("session_id is required in session payload.")

    db["sessions_raw"].insert_one(
        {
            "session_id": session_id,
            "source_file": str(file_path),
            "payload": payload,
            "ingested_at": utc_now_iso(),
        }
    )

    counts = {
        "playbooks": 0,
        "workflow_runs": 0,
        "domain_pages": 0,
        "decisions": 0,
        "profiles": 0,
        "innovations": 0,
        "blindspots": 0,
    }

    for playbook in payload.get("playbooks", []):
        slug = str(playbook["slug"]).strip()
        upsert_versioned(
            db,
            "workflow_playbooks",
            "slug",
            slug,
            {
                "title": playbook.get("title", slug),
                "summary": playbook.get("summary", ""),
                "steps": playbook.get("steps", []),
                "done_definition": playbook.get("done_definition", ""),
                "risks": playbook.get("risks", []),
                "tags": playbook.get("tags", []),
                "knowledge_scope": "session",
            },
        )
        counts["playbooks"] += 1

    date = payload.get("date", utc_now_iso()[0:10])
    for idx, todo in enumerate(payload.get("todos", []), start=1):
        run_id = str(todo.get("run_id") or f"{session_id}-todo-{idx}")
        upsert_versioned(
            db,
            "workflow_runs",
            "run_id",
            run_id,
            {
                "session_id": session_id,
                "date": date,
                "title": todo.get("title", run_id),
                "status": todo.get("status", "pending"),
                "plan": todo.get("plan", ""),
                "actual": todo.get("actual", ""),
                "deviation": todo.get("deviation", ""),
                "improvement": todo.get("improvement", ""),
                "workflow_slug": todo.get("workflow_slug", ""),
                "tags": todo.get("tags", []),
                "knowledge_scope": "session",
            },
        )
        counts["workflow_runs"] += 1

    for note in payload.get("domain_notes", []):
        slug = str(note["slug"]).strip()
        related = list(note.get("related_slugs", []))
        upsert_versioned(
            db,
            "domain_pages",
            "slug",
            slug,
            {
                "title": note.get("title", slug),
                "summary": note.get("summary", ""),
                "content": note.get("content", ""),
                "tags": note.get("tags", []),
                "related_slugs": related,
                "last_source_session": session_id,
                "knowledge_scope": "session",
            },
        )
        refresh_related_links(db, "domain_pages", slug, related)
        counts["domain_pages"] += 1

    for decision in payload.get("decisions", []):
        decision_id = str(decision["decision_id"]).strip()
        upsert_versioned(
            db,
            "decision_logs",
            "decision_id",
            decision_id,
            {
                "session_id": session_id,
                "title": decision.get("title", decision_id),
                "summary": decision.get("summary", ""),
                "reasoning": decision.get("reasoning", ""),
                "tradeoffs": decision.get("tradeoffs", []),
                "rejected_options": decision.get("rejected_options", []),
                "tags": decision.get("tags", []),
                "outcome": decision.get("outcome", ""),
                "knowledge_scope": "session",
            },
        )
        counts["decisions"] += 1

    for profile in payload.get("profile_updates", []):
        profile_key = str(profile.get("profile_key", "owner-default")).strip()
        upsert_versioned(
            db,
            "decision_profiles",
            "profile_key",
            profile_key,
            {
                "preferences": profile.get("preferences", {}),
                "notes": profile.get("notes", ""),
                "last_source_session": session_id,
                "knowledge_scope": "session",
            },
        )
        counts["profiles"] += 1

    for innovation in payload.get("innovations", []):
        innovation_id = str(innovation["innovation_id"]).strip()
        upsert_versioned(
            db,
            "innovation_logs",
            "innovation_id",
            innovation_id,
            {
                "session_id": session_id,
                "title": innovation.get("title", innovation_id),
                "hypothesis": innovation.get("hypothesis", ""),
                "validation_plan": innovation.get("validation_plan", ""),
                "result": innovation.get("result", ""),
                "tags": innovation.get("tags", []),
                "knowledge_scope": "session",
            },
        )
        counts["innovations"] += 1

    for blindspot in payload.get("blindspots", []):
        alert_id = str(blindspot["alert_id"]).strip()
        upsert_versioned(
            db,
            "blindspot_alerts",
            "alert_id",
            alert_id,
            {
                "session_id": session_id,
                "title": blindspot.get("title", alert_id),
                "category": blindspot.get("category", "general"),
                "trigger_rule": blindspot.get("trigger_rule", ""),
                "recommended_action": blindspot.get("recommended_action", ""),
                "status": blindspot.get("status", "active"),
                "tags": blindspot.get("tags", []),
                "knowledge_scope": "session",
            },
        )
        counts["blindspots"] += 1

    db["sync_state"].update_one(
        {"key": "last_ingested_session"},
        {"$set": {"key": "last_ingested_session", "value": session_id, "updated_at": utc_now_iso()}},
        upsert=True,
    )

    return counts
