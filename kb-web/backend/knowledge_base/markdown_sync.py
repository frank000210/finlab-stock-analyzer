from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import yaml
from pymongo.database import Database

from knowledge_base.config import load_settings
from knowledge_base.documents import refresh_related_links, utc_now_iso
from knowledge_base.vault_clean import sanitize_tags, strip_leading_history


SYNC_COLLECTIONS: dict[str, tuple[str, str]] = {
    "workflow_playbooks": ("slug", "workflow"),
    "workflow_runs": ("run_id", "workflow-run"),
    "domain_pages": ("slug", "domain"),
    "decision_profiles": ("profile_key", "decision-profile"),
    "decision_logs": ("decision_id", "decision"),
    "innovation_logs": ("innovation_id", "innovation"),
    "blindspot_alerts": ("alert_id", "blindspot"),
    "spec_docs": ("doc_id", "spec"),
    "swds_precedents": ("slug", "swds"),
    "ui_screens": ("screen_id", "ui-screen"),
}


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _slug_to_filename(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_")


def _build_front_matter(collection: str, key_field: str, doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection": collection,
        "key_field": key_field,
        "key_value": doc[key_field],
        "title": doc.get("title", doc[key_field]),
        "summary": doc.get("summary", ""),
        "tags": sanitize_tags(doc.get("tags", [])),
        "version": int(doc.get("version", 1)),
        "updated_at": doc.get("updated_at", utc_now_iso()),
    }


def _build_ui_screen_body(doc: dict[str, Any]) -> str:
    """Custom vault body for ui_screens: step-by-step with embedded screenshots."""
    scenario = doc.get("scenario", "")
    all_fields = doc.get("all_ui_fields", [])
    steps = doc.get("steps", [])

    lines = ["## 操作流程\n"]
    for step in steps:
        seq = step.get("seq", "?")
        desc = step.get("description", "")
        rel_path = step.get("screenshot_rel_path")
        ocr = step.get("ocr_text", "")
        elements = step.get("ui_elements", [])

        lines.append(f"### 步驟 {seq}")
        if desc:
            lines.append(f"\n{desc}\n")
        if elements:
            lines.append("**UI 元素：** " + "、".join(elements) + "\n")
        if rel_path:
            lines.append(f"![[{rel_path}]]\n")
        if ocr:
            lines.append("<details><summary>OCR 文字</summary>\n\n```\n" + ocr + "\n```\n</details>\n")

    if all_fields:
        lines.append("\n## 畫面欄位清單\n")
        for f in all_fields:
            lines.append(f"- {f}")

    lines.append("\n## Related Notes\n\n- (none)\n")
    return "\n".join(lines)


def _build_ppt_body(doc: dict[str, Any]) -> str:
    """Custom vault body for PPT presentation: all slide text blocks as a bulleted list."""
    source_file = doc.get("source_file", "")
    all_texts = doc.get("all_texts", [])
    summary = doc.get("summary", "")

    lines: list[str] = []
    if source_file:
        lines.append(f"**來源檔案：** `{source_file}`\n")
    if summary:
        lines.append(f"{summary}\n")

    if all_texts:
        lines.append("## 簡報內容\n")
        for text in all_texts:
            # Long texts (multi-line) as blockquote; short ones as bullet
            if "\n" in text or len(text) > 120:
                lines.append("\n> " + text.replace("\n", "\n> ") + "\n")
            else:
                lines.append(f"- {text}")

    lines.append("\n## Related Notes\n\n- (none)\n")
    return "\n".join(lines)


def _build_vsd_diagram_body(doc: dict[str, Any]) -> str:
    """Custom vault body for VSD diagrams: entity list for IM diagrams, step list for flowcharts."""
    diagram_type = doc.get("doc_type", "")
    entities = doc.get("vsd_entities", [])
    flow_steps = doc.get("flow_steps", [])
    summary = doc.get("summary", "")
    source_file = doc.get("source_file", "")

    lines: list[str] = []
    if source_file:
        lines.append(f"**來源檔案：** `{source_file}`\n")
    if summary:
        lines.append(f"{summary}\n")

    if diagram_type == "vsd-im-diagram" and entities:
        lines.append("## 資料模型實體\n")
        for ent in entities:
            name = ent.get("name", "")
            zh = ent.get("zh_name", "")
            attrs = ent.get("attributes", [])
            header = f"### {name}" + (f"（{zh}）" if zh else "")
            lines.append(header)
            if attrs:
                lines.append("**欄位：** " + "、".join(attrs[:20]))
                if len(attrs) > 20:
                    lines.append(f"…（共 {len(attrs)} 個欄位）")
            raw = ent.get("raw_text", "")
            if raw:
                lines.append("\n<details><summary>原始欄位說明</summary>\n\n```\n" + raw + "\n```\n</details>\n")
    elif flow_steps:
        lines.append("## 流程步驟\n")
        for i, step in enumerate(flow_steps, 1):
            lines.append(f"{i}. {step}")

    lines.append("\n## Related Notes\n\n- (none)\n")
    return "\n".join(lines)


def _build_body(collection: str, doc: dict[str, Any]) -> str:
    if collection == "ui_screens":
        return _build_ui_screen_body(doc)
    if collection == "spec_docs" and doc.get("doc_type", "").startswith("vsd-"):
        return _build_vsd_diagram_body(doc)
    if collection == "spec_docs" and doc.get("doc_type", "") == "ppt-presentation":
        return _build_ppt_body(doc)

    preferred = [
        "content",
        "reasoning",
        "hypothesis",
        "validation_plan",
        "result",
        "trigger_rule",
        "recommended_action",
        "notes",
        "plan",
        "actual",
        "deviation",
        "improvement",
        "done_definition",
    ]
    selected = ""
    for key in preferred:
        raw = doc.get(key)
        if isinstance(raw, str) and raw.strip():
            selected = raw
            break

    related = doc.get("related_slugs", [])
    related_lines = ""
    if isinstance(related, list) and related:
        related_lines = "\n".join(f"- [[{slug}]]" for slug in related)
    else:
        related_lines = "- (none)"

    payload_preview = {
        k: v
        for k, v in doc.items()
        if k
        not in {
            "_id",
            "created_at",
            "updated_at",
            "version",
        }
    }

    return (
        "## Content\n\n"
        f"{selected or '(empty)'}\n\n"
        "## Related Notes\n\n"
        f"{related_lines}\n\n"
        "## Structured Data\n\n"
        "```json\n"
        f"{json.dumps(payload_preview, ensure_ascii=False, indent=2)}\n"
        "```\n"
    )


def _render_markdown(front_matter: dict[str, Any], body: str) -> str:
    yaml_block = yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True).strip()
    title = front_matter.get("title") or front_matter["key_value"]
    return f"---\n{yaml_block}\n---\n\n# {title}\n\n{body}"


def _split_front_matter(markdown: str) -> tuple[dict[str, Any], str]:
    if not markdown.startswith("---\n"):
        raise ValueError("Missing YAML front matter header.")
    parts = markdown.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError("Malformed YAML front matter block.")
    fm_text = parts[0][4:]
    body = parts[1]
    front_matter = yaml.safe_load(fm_text)
    if not isinstance(front_matter, dict):
        raise ValueError("Front matter must be a YAML object.")
    return front_matter, body


def _iter_documents(db: Database) -> Iterable[tuple[str, str, dict[str, Any]]]:
    for collection, (key_field, _) in SYNC_COLLECTIONS.items():
        for doc in db[collection].find({}, projection={"_id": False}):
            yield collection, key_field, doc


def export_vault(db: Database) -> dict[str, int]:
    settings = load_settings()
    settings.vault_path.mkdir(parents=True, exist_ok=True)
    exported = 0

    for collection, key_field, doc in _iter_documents(db):
        collection_dir = settings.vault_path / collection
        collection_dir.mkdir(parents=True, exist_ok=True)

        if collection == "spec_docs":
            content = doc.get("content")
            if isinstance(content, str) and content.strip():
                trimmed, changed = strip_leading_history(content)
                if changed:
                    doc = {**doc, "content": trimmed}

        key_value = str(doc[key_field])
        file_name = f"{_slug_to_filename(key_value)}.md"
        path = collection_dir / file_name

        front_matter = _build_front_matter(collection, key_field, doc)
        body = _build_body(collection, doc)
        markdown = _render_markdown(front_matter, body)
        file_hash = _hash_text(markdown)

        path.write_text(markdown, encoding="utf-8")

        db["markdown_docs"].update_one(
            {"path": str(path)},
            {
                "$set": {
                    "path": str(path),
                    "collection": collection,
                    "document_key": key_value,
                    "exported_version": int(doc.get("version", 1)),
                    "file_hash": file_hash,
                    "last_synced_at": utc_now_iso(),
                }
            },
            upsert=True,
        )
        exported += 1

    db["sync_state"].update_one(
        {"key": "last_export"},
        {"$set": {"key": "last_export", "value": utc_now_iso(), "updated_at": utc_now_iso()}},
        upsert=True,
    )
    return {"exported": exported}


def import_vault(db: Database) -> dict[str, int]:
    settings = load_settings()
    if not settings.vault_path.exists():
        return {"imported": 0, "conflicts": 0, "skipped": 0}

    imported = 0
    conflicts = 0
    skipped = 0

    for path in settings.vault_path.rglob("*.md"):
        markdown = path.read_text(encoding="utf-8")
        file_hash = _hash_text(markdown)
        sync_doc = db["markdown_docs"].find_one({"path": str(path)})
        if sync_doc is not None and sync_doc.get("file_hash") == file_hash:
            skipped += 1
            continue

        try:
            front_matter, body = _split_front_matter(markdown)
        except ValueError:
            # Ignore user notes or plugin files that are not managed projection docs.
            if sync_doc is None:
                skipped += 1
                continue
            raise

        collection = str(front_matter.get("collection", "")).strip()
        key_field = str(front_matter.get("key_field", "")).strip()
        key_value = str(front_matter.get("key_value", "")).strip()
        incoming_version = int(front_matter.get("version", 0))

        if collection not in SYNC_COLLECTIONS:
            raise ValueError(f"Unsupported collection in file {path}: {collection}")
        expected_key_field = SYNC_COLLECTIONS[collection][0]
        if key_field != expected_key_field:
            raise ValueError(f"Invalid key_field in file {path}: {key_field}")
        if not key_value:
            raise ValueError(f"Missing key_value in file {path}")

        current = db[collection].find_one({key_field: key_value})
        if current is None:
            raise ValueError(
                f"Target document does not exist in MongoDB for {collection}.{key_field}={key_value}"
            )

        current_version = int(current.get("version", 0))
        if incoming_version != current_version:
            db["review_queue"].insert_one(
                {
                    "status": "pending",
                    "type": "version_conflict",
                    "path": str(path),
                    "collection": collection,
                    "key_field": key_field,
                    "key_value": key_value,
                    "incoming_version": incoming_version,
                    "current_version": current_version,
                    "incoming_front_matter": front_matter,
                    "incoming_body": body,
                    "created_at": utc_now_iso(),
                }
            )
            conflicts += 1
            continue

        title = str(front_matter.get("title", current.get("title", key_value)))
        summary = str(front_matter.get("summary", current.get("summary", "")))
        tags = front_matter.get("tags", current.get("tags", []))
        if not isinstance(tags, list):
            raise ValueError(f"tags must be a list in file {path}")

        update_payload: dict[str, Any] = {
            "title": title,
            "summary": summary,
            "tags": tags,
            "content": body.strip(),
            "updated_at": utc_now_iso(),
        }

        db[collection].update_one(
            {key_field: key_value},
            {"$set": update_payload, "$inc": {"version": 1}},
        )

        # Keep link graph in sync when markdown edits domain page relation metadata.
        if collection == "domain_pages":
            maybe_related = current.get("related_slugs", [])
            if isinstance(maybe_related, list):
                refresh_related_links(db, "domain_pages", key_value, maybe_related)

        refreshed = db[collection].find_one({key_field: key_value}, projection={"version": 1})
        if refreshed is None:
            raise RuntimeError(f"Failed to reload updated document for {collection}.{key_value}")

        db["markdown_docs"].update_one(
            {"path": str(path)},
            {
                "$set": {
                    "path": str(path),
                    "collection": collection,
                    "document_key": key_value,
                    "exported_version": int(refreshed.get("version", incoming_version + 1)),
                    "file_hash": file_hash,
                    "last_synced_at": utc_now_iso(),
                }
            },
            upsert=True,
        )
        imported += 1

    db["sync_state"].update_one(
        {"key": "last_import"},
        {"$set": {"key": "last_import", "value": utc_now_iso(), "updated_at": utc_now_iso()}},
        upsert=True,
    )

    return {"imported": imported, "conflicts": conflicts, "skipped": skipped}
