from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pymongo.database import Database

from knowledge_base.documents import utc_now_iso

TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}")
RULE_SIGNAL_PATTERN = re.compile(
    r"(受理|檢查|檢核|流程|步驟|Step\s*\d+|UseCase|聯單|竣工|批價|欄位)",
    re.IGNORECASE,
)


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if len(token.strip()) >= 2
    }


def _rule_signal_count(text: str) -> int:
    return len(RULE_SIGNAL_PATTERN.findall(text))


def _confidence_level(score: float, evidence_count: int, signal_count: int) -> tuple[str, bool]:
    if score >= 0.72 and evidence_count >= 3 and signal_count >= 6:
        return "high", True
    if score >= 0.45 and evidence_count >= 2:
        return "medium", False
    return "low", False


def _reference_documents(db: Database) -> list[dict[str, Any]]:
    refs = list(
        db["spec_docs"].find(
            {
                "$and": [
                    {"knowledge_scope": "spec"},
                    {"doc_type": {"$in": ["srs", "sds", "ref-manual"]}},
                ]
            },
            {"_id": False, "doc_id": True, "title": True, "doc_type": True, "content": True},
        )
    )
    for ref in refs:
        content = str(ref.get("content", ""))
        title = str(ref.get("title", ""))
        ref["__tokens"] = _tokenize(f"{title}\n{content[:12000]}")
    return refs


def validate_im_business_confidence(
    db: Database,
    doc_type: str = "im-spec",
    top_k_evidence: int = 5,
    report_path: Path | None = None,
) -> dict[str, Any]:
    refs = _reference_documents(db)
    im_docs = list(
        db["spec_docs"].find(
            {"$and": [{"knowledge_scope": "spec"}, {"doc_type": doc_type}]},
            {"_id": False, "doc_id": True, "title": True, "content": True, "ui_knowledge": True},
        )
    )

    validated = 0
    upgraded_to_medium = 0
    upgraded_to_high = 0
    still_low = 0
    needs_review = 0
    details: list[dict[str, Any]] = []

    for doc in im_docs:
        doc_id = str(doc.get("doc_id", ""))
        title = str(doc.get("title", ""))
        content = str(doc.get("content", ""))
        tokens = _tokenize(f"{title}\n{content[:15000]}")
        signal_count = _rule_signal_count(content)

        overlaps: list[dict[str, Any]] = []
        for ref in refs:
            ref_tokens = ref.get("__tokens", set())
            if not ref_tokens:
                continue
            shared = tokens.intersection(ref_tokens)
            if not shared:
                continue
            overlap_ratio = len(shared) / max(1, len(tokens))
            if overlap_ratio < 0.02:
                continue
            overlaps.append(
                {
                    "doc_id": ref.get("doc_id"),
                    "title": ref.get("title"),
                    "doc_type": ref.get("doc_type"),
                    "overlap_ratio": round(overlap_ratio, 4),
                    "shared_terms_preview": sorted(list(shared))[:10],
                }
            )

        overlaps.sort(key=lambda x: x["overlap_ratio"], reverse=True)
        evidence_docs = overlaps[:top_k_evidence]
        evidence_count = len(evidence_docs)
        overlap_avg = (
            sum(item["overlap_ratio"] for item in evidence_docs) / evidence_count if evidence_count else 0.0
        )

        ui_info = db["ui_knowledge"].find_one({"doc_id": doc_id}, {"_id": False, "field_mappings": True})
        mapping_count = len(ui_info.get("field_mappings", [])) if ui_info else 0

        score = (
            min(1.0, overlap_avg * 8.0) * 0.45
            + min(1.0, evidence_count / 5.0) * 0.25
            + min(1.0, signal_count / 20.0) * 0.2
            + min(1.0, mapping_count / 30.0) * 0.1
        )
        score = round(score, 4)
        level, verified = _confidence_level(score, evidence_count, signal_count)
        review_required = not verified

        if level == "high":
            upgraded_to_high += 1
        elif level == "medium":
            upgraded_to_medium += 1
        else:
            still_low += 1
        if review_required:
            needs_review += 1

        update_payload = {
            "business_confidence": level,
            "business_confidence_score": score,
            "business_confidence_verified": verified,
            "needs_business_review": review_required,
            "evidence_summary": {
                "evidence_count": evidence_count,
                "signal_count": signal_count,
                "field_mapping_count": mapping_count,
                "top_overlap_avg": round(overlap_avg, 4),
            },
            "evidence_docs": evidence_docs,
            "updated_at": utc_now_iso(),
        }
        db["spec_docs"].update_one({"doc_id": doc_id}, {"$set": update_payload})
        db["ui_knowledge"].update_one(
            {"doc_id": doc_id},
            {
                "$set": {
                    "business_confidence": level,
                    "business_confidence_score": score,
                    "business_confidence_verified": verified,
                    "needs_business_review": review_required,
                    "updated_at": utc_now_iso(),
                }
            },
        )
        db["im_validation_logs"].insert_one(
            {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "business_confidence": level,
                "business_confidence_score": score,
                "business_confidence_verified": verified,
                "review_required": review_required,
                "evidence_count": evidence_count,
                "signal_count": signal_count,
                "field_mapping_count": mapping_count,
                "evidence_docs": evidence_docs,
                "created_at": utc_now_iso(),
            }
        )

        details.append(
            {
                "doc_id": doc_id,
                "title": title,
                "business_confidence": level,
                "business_confidence_score": score,
                "verified": verified,
                "needs_business_review": review_required,
                "evidence_count": evidence_count,
                "signal_count": signal_count,
                "field_mapping_count": mapping_count,
                "evidence_preview": evidence_docs[:3],
            }
        )
        validated += 1

    result = {
        "doc_type": doc_type,
        "validated": validated,
        "upgraded_to_high": upgraded_to_high,
        "upgraded_to_medium": upgraded_to_medium,
        "still_low": still_low,
        "needs_business_review": needs_review,
        "details": details,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["report_path"] = str(report_path)

    return result

