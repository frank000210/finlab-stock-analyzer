from __future__ import annotations

from pathlib import Path
from typing import Any

from pymongo.database import Database

from knowledge_base.documents import utc_now_iso
from knowledge_base.eventlog_ingest import ingest_event_logs
from knowledge_base.markdown_sync import export_vault, import_vault
from knowledge_base.query import build_system_prompt_injection
from knowledge_base.semantic_search import rebuild_semantic_index


def on_session_open(
    db: Database,
    session_id: str,
    prompt_text: str,
    top_k: int = 5,
    scope: str = "session",
) -> dict[str, Any]:
    """Auto-inject knowledge context when a session starts."""
    if db["semantic_vectors"].estimated_document_count() == 0:
        rebuild_semantic_index(db)

    injection = build_system_prompt_injection(
        db=db,
        query_text=prompt_text,
        top_k=top_k,
        use_semantic=True,
        scope=scope,
    )
    db["sync_state"].update_one(
        {"key": f"session_open::{session_id}"},
        {
            "$set": {
                "key": f"session_open::{session_id}",
                "session_id": session_id,
                "prompt_text": prompt_text,
                "scope": scope,
                "injection": injection,
                "updated_at": utc_now_iso(),
            }
        },
        upsert=True,
    )
    return {
        "session_id": session_id,
        "has_context": bool(injection),
        "injection": injection,
    }


def on_session_close(
    db: Database,
    session_id: str,
    root_path: Path,
    profile_key: str = "owner-default",
    sync_after_ingest: bool = False,
) -> dict[str, Any]:
    """Auto-learn from the session's events.jsonl on session close."""
    ingest_counts = ingest_event_logs(
        db=db,
        root_path=root_path,
        profile_key=profile_key,
        include_session_ids={session_id},
    )
    semantic_counts = rebuild_semantic_index(db)

    sync_result: dict[str, Any] | None = None
    if sync_after_ingest:
        exported = export_vault(db)
        imported = import_vault(db)
        sync_result = {"export": exported, "import": imported}

    db["sync_state"].update_one(
        {"key": f"session_close::{session_id}"},
        {
            "$set": {
                "key": f"session_close::{session_id}",
                "session_id": session_id,
                "ingest_counts": ingest_counts,
                "semantic_counts": semantic_counts,
                "sync_after_ingest": sync_after_ingest,
                "updated_at": utc_now_iso(),
            }
        },
        upsert=True,
    )

    payload: dict[str, Any] = {
        "session_id": session_id,
        "ingest_counts": ingest_counts,
        "semantic_counts": semantic_counts,
    }
    if sync_result is not None:
        payload["sync"] = sync_result
    return payload
