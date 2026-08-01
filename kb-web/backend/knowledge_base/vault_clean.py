"""Vault noise cleanup helpers.

Two families of noise leaked into ``spec_docs`` during bulk ingestion and now
pollute the Obsidian graph and the knowledge base:

1. Auto-generated frontmatter ``tags`` full of document *structure* rather than
   *content* -- chapter/section headings (第一章 / 第一節), table-of-contents
   tokens (toc / pageref), ROC revision dates (970502 ...), source filenames
   (``*.md``) and ``key:value`` meta tags. Obsidian renders every distinct tag
   as a node, so these flood the graph view.

2. A leading 修訂歷程 / 版本沿革 (revision-history) block embedded at the top of
   the document body, which is metadata, not spec content.

This module centralises the sanitisation logic so it can be reused by the
ingest pipeline (``spec_ingest``), the markdown projection (``markdown_sync``)
and a one-off Mongo cleanup pass (``clean_spec_docs``).
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from pymongo.database import Database

from knowledge_base.documents import utc_now_iso

# --- tag sanitisation -------------------------------------------------------

# Pure numbers / ROC dates such as 970502, 1010512.
_NUMERIC_TAG = re.compile(r"^\d{2,7}$")
# 第一章 / 第 3 章 / 第二節 ... heading tokens.
_CHAPTER_TAG = re.compile(r"^第\s*[一二三四五六七八九十百零0-9]+\s*[章節]")
# Enumerated headings such as 一、 三. that slipped in as tags.
_ENUM_TAG = re.compile(r"^[一二三四五六七八九十]+\s*[、.．]")
# Word auto-generated bookmark / TOC anchors: _Toc276716409, _Hlk123, _Ref99, _GoBack.
_ANCHOR_TAG = re.compile(r"^_(toc|hlk|ref|bookmark|goback)\w*$", re.IGNORECASE)
# Any underscore-led token ending in a run of digits is an anchor, e.g. _toc276716409.
_ANCHOR_NUM_TAG = re.compile(r"^_[a-z]*\d{2,}$", re.IGNORECASE)
# Document filename extensions that leak in as tags.
_FILENAME_EXTS = (
    ".md",
    ".txt",
    ".rst",
    ".doc",
    ".docx",
    ".pdf",
    ".xls",
    ".xlsx",
    ".csv",
    ".ppt",
    ".pptx",
    ".vsd",
)

# Generic ASCII structure/boilerplate words (lower-cased comparison).
_ASCII_STOPWORDS: frozenset[str] = frozenset(
    {
        "toc",
        "pageref",
        "introduction",
        "document",
        "documents",
        "spec",
        "specs",
        "doc",
        "docs",
        "tag",
        "tags",
        "mermaid",
        "subgraph",
        "flowchart",
        "erdiagram",
        "graph",
        "diagram",
        "contents",
        "content",
        "index",
        "overview",
        "appendix",
        "revision",
        "revisions",
        "changelog",
        "history",
        "srs",
        "sds",
        "prd",
        "adr",
        "page",
        "pages",
        "section",
        "sections",
        "chapter",
        "title",
        "summary",
    }
)

# Chinese document-structure / history / boilerplate section titles.
_CJK_STOPWORDS: frozenset[str] = frozenset(
    {
        "介紹",
        "使用對象",
        "使用說明",
        "產品說明",
        "申請方式",
        "選單規劃",
        "畫面流程圖",
        "輸入",
        "輸出",
        "輸出欄位說明",
        "欄位說明",
        "聯單流控",
        "繳費",
        "配卡",
        "產生聯單",
        "查詢作業",
        "業務簡介",
        "前言",
        "目錄",
        "修訂",
        "修訂紀錄",
        "修訂記錄",
        "修訂歷程",
        "版本",
        "版本歷程",
        "版次",
        "版本沿革",
        "文件修改歷程",
        "文件歷程",
        "文件修訂歷程",
        "異動紀錄",
        "變更歷程",
        "修改記錄",
        "文件資訊",
        "文件目的",
        "文件說明",
        "參考文件",
        "名詞定義",
        "附錄",
        "待刪除",
        "舊",
        # revision-history table column headers / values
        "作者",
        "修改人",
        "修訂人",
        "修訂者",
        "修改內容",
        "修改說明",
        "異動說明",
        "異動版本說明",
        "版本說明",
        "日期",
        "修改日期",
        "制定日期",
        "生效日期",
        "初版",
        "舊版",
        "新版",
        "制訂",
        "制定",
        "制表",
        "製表",
        "核准",
        "審核",
        "頁次",
        "編號",
    }
)


def is_noise_tag(tag: str) -> bool:
    """Return ``True`` when a tag is document structure/history, not content."""
    token = (tag or "").strip()
    if not token:
        return True
    if ":" in token:  # key:value meta tags (business_confidence:low ...)
        return True
    if token.lower().endswith(_FILENAME_EXTS):  # source filenames
        return True
    if _ANCHOR_TAG.match(token) or _ANCHOR_NUM_TAG.match(token):  # Word TOC/bookmark anchors
        return True
    if _NUMERIC_TAG.match(token):  # ROC dates / bare numbers
        return True
    if _CHAPTER_TAG.match(token):
        return True
    if _ENUM_TAG.match(token):
        return True
    if token.lower() in _ASCII_STOPWORDS:
        return True
    if token in _CJK_STOPWORDS:
        return True
    return False


def sanitize_tags(tags: Iterable[Any]) -> list[str]:
    """Drop structure/history noise tags and return a sorted, de-duplicated list."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        if not isinstance(raw, str):
            continue
        token = raw.strip()
        if is_noise_tag(token):
            continue
        if token in seen:
            continue
        seen.add(token)
        kept.append(token)
    return sorted(kept)


# --- body revision-history trimming ----------------------------------------

_HISTORY_HEADING_PATTERNS = [
    re.compile(
        r"^\s*#*\s*(修訂紀錄|修訂記錄|修訂歷程|版本沿革|版本歷程|文件修改歷程|文件修訂歷程|"
        r"文件歷程|異動紀錄|變更歷程|修改記錄|revision\s*history|change\s*log)\s*[:：]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*#*\s*(版次|版本|修訂|變更)\s*(紀錄|記錄|歷程)?\s*[:：]?\s*$", re.IGNORECASE),
]

# Strong, unambiguous body-start markers. Deliberately excludes bare "\d+.\d+"
# numeric patterns because revision-history rows (e.g. "1.0 2020 初版") match
# them and would stop the trim too early, leaving history rows behind.
_STRONG_BODY_PATTERNS = [
    re.compile(r"^\s*#*\s*第\s*[一二三四五六七八九十百零0-9]+\s*章"),
    re.compile(r"^\s*#*\s*[一二三四五六七八九十]+\s*[、.．]\s*\S+"),
]


def _is_history_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in _HISTORY_HEADING_PATTERNS)


def _is_body_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in _STRONG_BODY_PATTERNS)


def strip_leading_history(content: str) -> tuple[str, bool]:
    """Remove a leading revision-history block that precedes the first chapter.

    Conservative by design: only trims when a history heading is found *and* an
    unambiguous chapter/section heading (第X章 / 一、) follows it. If no strong
    body marker is found the content is returned untouched, so real content is
    never removed.
    """
    if not content:
        return content, False
    lines = content.splitlines()
    window = min(len(lines), 300)

    history_idx: int | None = None
    for idx in range(window):
        if _is_history_heading(lines[idx].strip()):
            history_idx = idx
            break
    if history_idx is None:
        return content, False

    body_idx: int | None = None
    for idx in range(history_idx + 1, window):
        line = lines[idx].strip()
        if not line:
            continue
        if _is_body_heading(line):
            body_idx = idx
            break
    if body_idx is None or body_idx <= history_idx:
        return content, False

    trimmed = "\n".join(lines[body_idx:]).strip()
    if not trimmed:
        return content, False
    return trimmed, True


# --- one-off Mongo cleanup pass --------------------------------------------


def clean_spec_docs(db: Database, *, apply: bool = False) -> dict[str, Any]:
    """Sanitise tags and trim leading revision-history for every ``spec_docs`` doc.

    When ``apply`` is False (default) the pass is a dry-run and reports how many
    documents *would* change without writing anything.
    """
    scanned = 0
    tags_changed = 0
    history_trimmed = 0
    tags_removed_total = 0
    samples: list[dict[str, Any]] = []

    for doc in db["spec_docs"].find(
        {}, projection={"doc_id": 1, "tags": 1, "content": 1}
    ):
        scanned += 1
        doc_id = doc.get("doc_id", "")
        original_tags = doc.get("tags", []) or []
        new_tags = sanitize_tags(original_tags)
        original_content = doc.get("content", "") or ""
        new_content, trimmed = strip_leading_history(original_content)

        update: dict[str, Any] = {}
        if new_tags != sorted(t for t in original_tags if isinstance(t, str)):
            update["tags"] = new_tags
            tags_changed += 1
            tags_removed_total += max(0, len(set(original_tags)) - len(new_tags))
        if trimmed:
            update["content"] = new_content
            history_trimmed += 1

        if not update:
            continue

        if len(samples) < 8:
            samples.append(
                {
                    "doc_id": doc_id,
                    "tags_before": len(set(original_tags)),
                    "tags_after": len(new_tags) if "tags" in update else len(original_tags),
                    "history_trimmed": trimmed,
                }
            )

        if apply:
            update["updated_at"] = utc_now_iso()
            db["spec_docs"].update_one({"doc_id": doc_id}, {"$set": update})

    return {
        "applied": apply,
        "scanned": scanned,
        "tags_changed": tags_changed,
        "history_trimmed": history_trimmed,
        "tags_removed_total": tags_removed_total,
        "samples": samples,
    }
