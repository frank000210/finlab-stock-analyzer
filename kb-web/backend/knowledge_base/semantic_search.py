from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from pymongo.database import Database

from knowledge_base.documents import utc_now_iso

VECTOR_DIM = 384  # sentence-transformers paraphrase-multilingual-MiniLM-L12-v2
VECTOR_DIM_FALLBACK = 256  # legacy hashing-v1
SEMANTIC_COLLECTION = "semantic_vectors"
_ST_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_st_model = None  # lazy-loaded


def _load_st_model():
    """Lazy-load the SentenceTransformer model (downloads on first use)."""
    import os
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _st_model = SentenceTransformer(_ST_MODEL_NAME)
    return _st_model


def _st_embedding(text: str) -> list[float]:
    """Generate a 384-dim semantic embedding using sentence-transformers."""
    model = _load_st_model()
    vec = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    return [float(v) for v in vec]


def _embedding_backend_available() -> bool:
    """Return True when sentence-transformers is importable."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False

TARGET_COLLECTIONS = {
    "domain_pages": {"key_field": "slug", "title_field": "title"},
    "decision_logs": {"key_field": "decision_id", "title_field": "title"},
    "blindspot_alerts": {"key_field": "alert_id", "title_field": "title"},
    "workflow_runs": {"key_field": "run_id", "title_field": "title"},
    "innovation_logs": {"key_field": "innovation_id", "title_field": "title"},
    "spec_docs": {"key_field": "doc_id", "title_field": "title"},
    "swds_precedents": {"key_field": "slug", "title_field": "title"},
    "ui_screens": {"key_field": "screen_id", "title_field": "title"},
}


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin_tokens = re.findall(r"[a-z0-9_]{2,}", lowered)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_bigrams: list[str] = []
    for chunk in cjk_chunks:
        if len(chunk) <= 2:
            cjk_bigrams.append(chunk)
            continue
        cjk_bigrams.extend(chunk[i : i + 2] for i in range(0, len(chunk) - 1))
    return latin_tokens + cjk_chunks + cjk_bigrams


def _norm(vector: list[float]) -> list[float]:
    size = math.sqrt(sum(v * v for v in vector))
    if size == 0:
        return vector
    return [v / size for v in vector]


def _hashing_embedding(text: str, dim: int = VECTOR_DIM_FALLBACK) -> list[float]:
    """Legacy 256-dim bag-of-words hash embedding (fallback only)."""
    vec = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    return _norm(vec)


def _embed(text: str) -> tuple[list[float], str]:
    """Return (vector, backend_name). Uses ST when available, else hash fallback."""
    if _embedding_backend_available():
        return _st_embedding(text), "sentence-transformers-v1"
    return _hashing_embedding(text), "hashing-v1"


def _cosine(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return float(sum(a * b for a, b in zip(v1, v2)))


def _compose_text(collection: str, doc: dict[str, Any]) -> str:
    if collection == "domain_pages":
        parts = [doc.get("title", ""), doc.get("summary", ""), doc.get("content", "")]
    elif collection == "decision_logs":
        parts = [doc.get("title", ""), doc.get("summary", ""), doc.get("reasoning", "")]
    elif collection == "blindspot_alerts":
        parts = [
            doc.get("title", ""),
            doc.get("trigger_rule", ""),
            doc.get("recommended_action", ""),
        ]
    elif collection == "workflow_runs":
        parts = [
            doc.get("title", ""),
            doc.get("plan", ""),
            doc.get("actual", ""),
            doc.get("improvement", ""),
        ]
    elif collection == "innovation_logs":
        parts = [
            doc.get("title", ""),
            doc.get("hypothesis", ""),
            doc.get("validation_plan", ""),
            doc.get("result", ""),
        ]
    elif collection == "spec_docs":
        parts = [
            doc.get("title", ""),
            doc.get("summary", ""),
            doc.get("content", ""),
            doc.get("doc_type", ""),
            doc.get("relative_path", ""),
        ]
    elif collection == "swds_precedents":
        parts = [
            doc.get("title", ""),
            doc.get("category", ""),
            doc.get("requirement_text", ""),
            " ".join(str(v) for v in doc.get("table_names", [])),
            " ".join(str(v) for v in doc.get("function_names", [])),
        ]
    elif collection == "ui_screens":
        step_descriptions = " ".join(
            s.get("description", "") for s in doc.get("steps", [])
        )
        ocr_texts = " ".join(
            s.get("ocr_text", "") for s in doc.get("steps", []) if s.get("ocr_text")
        )
        parts = [
            doc.get("title", ""),
            doc.get("scenario", ""),
            doc.get("summary", ""),
            step_descriptions,
            " ".join(str(f) for f in doc.get("all_ui_fields", [])),
            ocr_texts,
        ]
    else:
        parts = [str(doc)]
    tags = " ".join(str(v) for v in doc.get("tags", []))
    return " ".join([*parts, tags]).strip()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rebuild_semantic_index(
    db: Database,
    collections: list[str] | None = None,
    force: bool = False,
) -> dict[str, int]:
    target_collections = collections or list(TARGET_COLLECTIONS.keys())
    total_seen = 0
    total_indexed = 0
    total_skipped = 0

    for collection in target_collections:
        if collection not in TARGET_COLLECTIONS:
            continue
        key_field = TARGET_COLLECTIONS[collection]["key_field"]
        title_field = TARGET_COLLECTIONS[collection]["title_field"]
        for doc in db[collection].find({}):
            key_value = str(doc.get(key_field, "")).strip()
            if not key_value:
                continue
            total_seen += 1

            text = _compose_text(collection, doc)
            if not text:
                total_skipped += 1
                continue
            digest = _text_hash(text)

            existing = db[SEMANTIC_COLLECTION].find_one(
                {"collection": collection, "key_field": key_field, "key_value": key_value}
            )
            if existing is not None and not force and existing.get("text_hash") == digest:
                total_skipped += 1
                continue

            vector, backend = _embed(text)
            db[SEMANTIC_COLLECTION].update_one(
                {"collection": collection, "key_field": key_field, "key_value": key_value},
                {
                    "$set": {
                        "collection": collection,
                        "key_field": key_field,
                        "key_value": key_value,
                        "title": str(doc.get(title_field, key_value)),
                        "summary": str(doc.get("summary", "")),
                        "tags": doc.get("tags", []),
                        "text_hash": digest,
                        "vector_dim": len(vector),
                        "vector": vector,
                        "embedding_backend": backend,
                        "knowledge_scope": str(doc.get("knowledge_scope", "session")),
                        "updated_at": utc_now_iso(),
                    },
                    "$setOnInsert": {"created_at": utc_now_iso()},
                },
                upsert=True,
            )
            total_indexed += 1

    return {
        "seen": total_seen,
        "indexed": total_indexed,
        "skipped": total_skipped,
    }


def semantic_search(
    db: Database,
    query_text: str,
    top_k: int = 5,
    min_score: float = 0.15,
    include_collections: list[str] | None = None,
    scope: str = "all",
) -> list[dict[str, Any]]:
    query_vector, _ = _embed(query_text)
    matcher: dict[str, Any] = {}
    if include_collections:
        matcher["collection"] = {"$in": include_collections}
    if scope != "all":
        matcher["knowledge_scope"] = scope

    rows = list(db[SEMANTIC_COLLECTION].find(matcher))
    scored: list[dict[str, Any]] = []
    type_map = {
        "domain_pages": "domain",
        "decision_logs": "decision",
        "blindspot_alerts": "blindspot",
        "workflow_runs": "workflow",
        "innovation_logs": "innovation",
        "spec_docs": "spec",
        "swds_precedents": "swds",
        "ui_screens": "ui-screen",
    }

    for row in rows:
        vector = row.get("vector", [])
        if not isinstance(vector, list):
            continue
        score = _cosine(query_vector, [float(v) for v in vector])
        if score < min_score:
            continue

        collection = str(row.get("collection", ""))
        key_field = str(row.get("key_field", ""))
        key_value = str(row.get("key_value", ""))
        source_doc = db[collection].find_one({key_field: key_value}) if collection and key_field else None
        if source_doc is None:
            continue

        scored.append(
            {
                "doc": source_doc,
                "type": type_map.get(collection, "unknown"),
                "relevance_score": max(1.0, score * 10.0),
                "source": "semantic",
                "semantic_score": score,
            }
        )

    scored.sort(key=lambda x: x["semantic_score"], reverse=True)
    return scored[:top_k]
