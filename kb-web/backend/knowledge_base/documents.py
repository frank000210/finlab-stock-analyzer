from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_versioned(
    db: Database,
    collection_name: str,
    key_field: str,
    key_value: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    collection = db[collection_name]
    current = collection.find_one({key_field: key_value})

    if current is None:
        document = {
            key_field: key_value,
            "version": 1,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            **payload,
        }
        collection.insert_one(document)
        return document

    next_version = int(current.get("version", 0)) + 1
    updates = {
        "$set": {**payload, "updated_at": utc_now_iso()},
        "$setOnInsert": {"created_at": current.get("created_at", utc_now_iso())},
        "$inc": {"version": 1},
    }
    collection.update_one({key_field: key_value}, updates)
    merged = collection.find_one({key_field: key_value})
    if merged is None:
        raise RuntimeError(
            f"Failed to load updated document: {collection_name}.{key_field}={key_value}"
        )
    if int(merged.get("version", 0)) != next_version:
        raise RuntimeError(
            f"Version mismatch after update: {collection_name}.{key_field}={key_value}"
        )
    return merged


def refresh_related_links(
    db: Database,
    from_collection: str,
    from_slug: str,
    related_slugs: list[str],
) -> None:
    links = db["links_graph"]
    links.delete_many(
        {
            "from_collection": from_collection,
            "from_slug": from_slug,
            "relation": "related",
        }
    )
    for target in related_slugs:
        links.update_one(
            {"from_slug": from_slug, "to_slug": target, "relation": "related"},
            {
                "$set": {
                    "from_collection": from_collection,
                    "from_slug": from_slug,
                    "to_slug": target,
                    "relation": "related",
                    "updated_at": utc_now_iso(),
                },
                "$setOnInsert": {"created_at": utc_now_iso()},
            },
            upsert=True,
        )

