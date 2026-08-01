from __future__ import annotations

from pymongo.database import Database


COLLECTIONS = [
    "sessions_raw",
    "workflow_playbooks",
    "workflow_runs",
    "domain_pages",
    "decision_profiles",
    "decision_logs",
    "innovation_logs",
    "blindspot_alerts",
    "links_graph",
    "sync_state",
    "review_queue",
    "markdown_docs",
    "semantic_vectors",
    "spec_docs",
    "ui_knowledge",
    "im_validation_logs",
    "swds_precedents",
    "ui_screens",
]


def init_schema(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)

    db["sessions_raw"].create_index([("session_id", 1), ("ingested_at", -1)])

    db["workflow_playbooks"].create_index("slug", unique=True)
    db["workflow_runs"].create_index("run_id", unique=True)
    db["workflow_runs"].create_index([("date", -1), ("status", 1)])
    db["workflow_runs"].create_index([("knowledge_scope", 1)])

    db["domain_pages"].create_index("slug", unique=True)
    db["domain_pages"].create_index([("tags", 1)])
    db["domain_pages"].create_index([("knowledge_scope", 1)])

    db["decision_profiles"].create_index("profile_key", unique=True)
    db["decision_logs"].create_index("decision_id", unique=True)
    db["decision_logs"].create_index([("tags", 1)])
    db["decision_logs"].create_index([("knowledge_scope", 1)])

    db["innovation_logs"].create_index("innovation_id", unique=True)
    db["innovation_logs"].create_index([("tags", 1)])
    db["innovation_logs"].create_index([("knowledge_scope", 1)])

    db["blindspot_alerts"].create_index("alert_id", unique=True)
    db["blindspot_alerts"].create_index([("category", 1), ("status", 1)])
    db["blindspot_alerts"].create_index([("knowledge_scope", 1)])

    db["links_graph"].create_index(
        [("from_slug", 1), ("to_slug", 1), ("relation", 1)], unique=True
    )

    db["sync_state"].create_index("key", unique=True)
    db["review_queue"].create_index([("status", 1), ("created_at", -1)])

    db["markdown_docs"].create_index("path", unique=True)
    db["markdown_docs"].create_index(
        [("collection", 1), ("document_key", 1)], unique=True
    )

    db["semantic_vectors"].create_index(
        [("collection", 1), ("key_field", 1), ("key_value", 1)],
        unique=True,
    )
    db["semantic_vectors"].create_index([("tags", 1)])
    db["semantic_vectors"].create_index([("knowledge_scope", 1)])

    db["spec_docs"].create_index("doc_id", unique=True)
    db["spec_docs"].create_index([("doc_type", 1)])
    db["spec_docs"].create_index([("tags", 1)])
    db["spec_docs"].create_index([("knowledge_scope", 1)])

    db["ui_knowledge"].create_index("ui_doc_id", unique=True)
    db["ui_knowledge"].create_index([("doc_type", 1)])
    db["ui_knowledge"].create_index([("knowledge_scope", 1)])
    db["ui_knowledge"].create_index([("needs_ui_review", 1)])

    db["im_validation_logs"].create_index([("doc_id", 1), ("created_at", -1)])
    db["im_validation_logs"].create_index([("doc_type", 1), ("created_at", -1)])
    db["im_validation_logs"].create_index([("business_confidence", 1)])

    db["swds_precedents"].create_index("slug", unique=True)
    db["swds_precedents"].create_index([("category", 1)])
    db["swds_precedents"].create_index([("tags", 1)])
    db["swds_precedents"].create_index([("table_names", 1)])
    db["swds_precedents"].create_index([("knowledge_scope", 1)])

    db["ui_screens"].create_index("screen_id", unique=True)
    db["ui_screens"].create_index([("scenario", 1)])
    db["ui_screens"].create_index([("tags", 1)])
    db["ui_screens"].create_index([("all_ui_fields", 1)])
    db["ui_screens"].create_index([("knowledge_scope", 1)])
