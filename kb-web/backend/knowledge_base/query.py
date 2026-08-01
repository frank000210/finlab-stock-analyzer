"""Query and retrieval module for knowledge base."""

from __future__ import annotations

import re
from typing import Any

from pymongo.database import Database

from knowledge_base.semantic_search import semantic_search

SESSION_SCOPE_COLLECTIONS = [
    "domain_pages",
    "decision_logs",
    "blindspot_alerts",
    "workflow_runs",
    "innovation_logs",
]
SPEC_SCOPE_COLLECTIONS = ["spec_docs", "swds_precedents", "ui_screens"]


def extract_keywords(text: str) -> list[str]:
    """Extract keywords from mixed EN/ZH text for searching."""
    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "must",
        "that",
        "this",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "of",
        "to",
        "from",
        "up",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "over",
        "out",
        "off",
        "if",
        "unless",
        "as",
        "also",
        "so",
        "while",
        "some",
        "any",
        "each",
        "every",
        "both",
    }
    lowered = text.lower()
    words = [w for w in re.findall(r"\b[a-z0-9_-]+\b", lowered) if w not in stopwords and len(w) > 2]

    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_bigrams: list[str] = []
    for chunk in cjk_chunks:
        if len(chunk) <= 2:
            cjk_bigrams.append(chunk)
        else:
            cjk_bigrams.extend(chunk[i : i + 2] for i in range(0, len(chunk) - 1))

    keywords = list(dict.fromkeys([*words, *cjk_chunks, *cjk_bigrams]))
    return keywords


def _merge_result(
    merged: dict[str, dict[str, Any]],
    key: str,
    item: dict[str, Any],
) -> None:
    previous = merged.get(key)
    if previous is None or float(item.get("relevance_score", 0.0)) > float(previous.get("relevance_score", 0.0)):
        merged[key] = item


def _collection_lexical_search(
    db: Database,
    collection: str,
    doc_type: str,
    key_field: str,
    keywords: list[str],
    include_tags: list[str] | None,
    limit: int,
    weight: float,
) -> list[dict[str, Any]]:
    if include_tags:
        matcher: dict[str, Any] = {"$and": [{"tags": {"$in": keywords}}, {"tags": {"$in": include_tags}}]}
    else:
        matcher = {"tags": {"$in": keywords}}

    results: list[dict[str, Any]] = []
    for doc in db[collection].find(matcher).limit(limit):
        key_value = str(doc.get(key_field, "")).strip()
        if not key_value:
            continue
        tags = doc.get("tags", [])
        matched_tags = len([t for t in tags if t in keywords]) if isinstance(tags, list) else 0
        relevance = matched_tags * weight + 1.0
        results.append(
            {
                "doc": doc,
                "type": doc_type,
                "relevance_score": relevance,
                "source": "lexical",
            }
        )
    return results


def search_knowledge(
    db: Database,
    query_text: str,
    top_k: int = 5,
    include_tags: list[str] | None = None,
    use_semantic: bool = True,
    scope: str = "session",
) -> list[dict[str, Any]]:
    """
    Search for related knowledge.

    Merges lexical tag search + semantic vector similarity.
    """
    keywords = extract_keywords(query_text)
    if not keywords and not use_semantic:
        return []

    merged: dict[str, dict[str, Any]] = {}

    lexical_specs = [
        ("domain_pages", "domain", "slug", 3 * top_k, 10.0),
        ("decision_logs", "decision", "decision_id", 3 * top_k, 8.0),
        ("blindspot_alerts", "blindspot", "alert_id", 2 * top_k, 6.0),
        ("workflow_runs", "workflow", "run_id", 2 * top_k, 4.0),
        ("innovation_logs", "innovation", "innovation_id", top_k, 3.0),
        ("spec_docs", "spec", "doc_id", 3 * top_k, 9.0),
        ("ui_screens", "ui-screen", "screen_id", 2 * top_k, 8.5),
    ]
    if scope == "session":
        allowed = set(SESSION_SCOPE_COLLECTIONS)
    elif scope == "spec":
        allowed = set(SPEC_SCOPE_COLLECTIONS)
    elif scope == "all":
        allowed = set(SESSION_SCOPE_COLLECTIONS + SPEC_SCOPE_COLLECTIONS)
    else:
        raise ValueError(f"Unsupported scope: {scope}")

    if keywords:
        for collection, doc_type, key_field, limit, weight in lexical_specs:
            if collection not in allowed:
                continue
            for item in _collection_lexical_search(
                db=db,
                collection=collection,
                doc_type=doc_type,
                key_field=key_field,
                keywords=keywords,
                include_tags=include_tags,
                limit=limit,
                weight=weight,
            ):
                key = f"{doc_type}:{item['doc'].get(key_field, '')}"
                _merge_result(merged, key, item)

    if use_semantic:
        semantic_results = semantic_search(
            db=db,
            query_text=query_text,
            top_k=max(top_k * 2, 10),
            include_collections=sorted(allowed),
            scope="all" if scope == "all" else scope,
        )
        for item in semantic_results:
            doc = item["doc"]
            key_value = (
                doc.get("slug")
                or doc.get("decision_id")
                or doc.get("alert_id")
                or doc.get("run_id")
                or doc.get("innovation_id")
                or doc.get("doc_id")
                or doc.get("screen_id")
                or ""
            )
            key = f"{item['type']}:{key_value}"
            existing = merged.get(key)
            if existing is None:
                _merge_result(merged, key, item)
                continue
            # Prefer lexical score if much stronger, otherwise combine both.
            combined = dict(existing)
            combined["source"] = "hybrid"
            combined["semantic_score"] = item.get("semantic_score", 0.0)
            combined["relevance_score"] = float(existing.get("relevance_score", 0.0)) + float(
                item.get("relevance_score", 0.0)
            ) * 0.35
            _merge_result(merged, key, combined)

    final_results = sorted(merged.values(), key=lambda x: float(x["relevance_score"]), reverse=True)
    return final_results[:top_k]


def format_knowledge_context(
    results: list[dict[str, Any]],
    max_chars: int = 2200,
) -> str:
    """Format search results into system-prompt-friendly markdown."""
    if not results:
        return ""

    lines = ["## Knowledge Base Context (Retrieved Insights):\n"]
    current_chars = 0

    for item in results:
        doc = item["doc"]
        doc_type = item["type"]

        if doc_type == "domain":
            title = doc.get("title", "Unknown")
            summary = doc.get("summary", "")
            section = f"**[Domain] {title}**: {summary}"
        elif doc_type == "decision":
            title = doc.get("title", "Decision")
            summary = doc.get("summary", "")
            reasoning = str(doc.get("reasoning", ""))[:180]
            section = f"**[Decision] {title}**: {summary} (_Reasoning: {reasoning}_)"
        elif doc_type == "blindspot":
            category = doc.get("category", "risk")
            title = doc.get("title", "Blindspot")
            action = str(doc.get("recommended_action", ""))[:180]
            section = f"**[Blindspot:{category}] {title}**: {action}"
        elif doc_type == "workflow":
            title = doc.get("title", "Workflow")
            plan = str(doc.get("plan", ""))[:160]
            section = f"**[Workflow] {title}**: {plan}"
        elif doc_type == "innovation":
            title = doc.get("title", "Idea")
            hypothesis = str(doc.get("hypothesis", ""))[:160]
            section = f"**[Innovation] {title}**: {hypothesis}"
        elif doc_type == "spec":
            title = doc.get("title", "Spec")
            doc_type_name = doc.get("doc_type", "spec")
            summary = str(doc.get("summary", ""))[:180]
            # VSD diagrams: show entity names for IM diagrams, or step count for flowcharts
            if doc_type_name == "vsd-im-diagram":
                table_names = ", ".join(doc.get("table_names", [])[:8])
                section = f"**[VSD-IM] {title}**: 資料表：{table_names}"
            elif doc_type_name == "vsd-flowchart":
                steps = doc.get("flow_steps", [])
                section = f"**[VSD-流程] {title}**: {len(steps)} 個流程節點 — " + "→".join(steps[:5])
            elif doc_type_name == "ppt-presentation":
                texts = doc.get("all_texts", [])
                preview = "、".join(t[:20] for t in texts[:4] if t)
                section = f"**[PPT] {title}**: {preview}"
            else:
                section = f"**[Spec:{doc_type_name}] {title}**: {summary}"
        elif doc_type == "ui-screen":
            title = doc.get("title", "UI Screen")
            scenario = doc.get("scenario", "")
            fields = "、".join(doc.get("all_ui_fields", [])[:8])
            section = f"**[UI:{scenario}] {title}**: 欄位：{fields}"
        else:
            section = str(doc)[:200]

        section_with_newline = f"- {section}\n"
        if current_chars + len(section_with_newline) > max_chars:
            break
        lines.append(section_with_newline)
        current_chars += len(section_with_newline)

    return "".join(lines)


def build_system_prompt_injection(
    db: Database,
    query_text: str,
    top_k: int = 5,
    use_semantic: bool = True,
    scope: str = "session",
) -> str:
    """Generate system prompt injection for session context."""
    results = search_knowledge(
        db=db,
        query_text=query_text,
        top_k=top_k,
        use_semantic=use_semantic,
        scope=scope,
    )
    context = format_knowledge_context(results)
    if not context:
        return ""

    return f"""You have access to historical knowledge compiled from previous sessions.
Use it to produce consistent, context-aware answers:

{context}

When answering:
- Reuse proven workflows before inventing new ones.
- Respect prior decision patterns unless the new constraints differ.
- Surface known blindspots early and suggest mitigations.
- Mention when current advice intentionally deviates from past patterns.
"""
