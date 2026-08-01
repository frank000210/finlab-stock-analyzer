"""VSD (Visio) diagram ingestion via LibreOffice SVG conversion + SVG text extraction.

Pipeline:
  VSD (OLE binary)
    -> LibreOffice soffice --headless --convert-to svg
    -> SVG text extraction (xml.etree.ElementTree)
    -> IM entity / flowchart step parsing
    -> spec_docs upsert (doc_type: vsd-im-diagram | vsd-flowchart)
    -> semantic index rebuild (caller's responsibility)

doc_id format:  vsd-<slug>   e.g. vsd-im-優惠規劃設定
collection:     spec_docs
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from pymongo.database import Database

from knowledge_base.documents import upsert_versioned, utc_now_iso
from knowledge_base.vault_clean import sanitize_tags

# ── LibreOffice discovery ─────────────────────────────────────────────────────

_LO_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def _find_libreoffice() -> str | None:
    """Return path to soffice.exe or None if LibreOffice is not installed."""
    for p in _LO_CANDIDATES:
        if Path(p).exists():
            return p
    found = shutil.which("soffice")
    return found


# ── SVG text extraction ───────────────────────────────────────────────────────

_SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def _extract_svg_texts(svg_path: Path) -> list[str]:
    """Return a deduplicated list of non-empty text strings from an SVG file."""
    tree = ET.parse(str(svg_path))
    root = tree.getroot()
    texts: list[str] = []
    seen: set[str] = set()
    for el in root.findall(".//svg:text", _SVG_NS):
        parts: list[str] = []
        for sub in el.iter():
            if sub.text and sub.text.strip():
                parts.append(sub.text.strip())
            if sub.tail and sub.tail.strip():
                parts.append(sub.tail.strip())
        combined = " ".join(parts).strip()
        if combined and combined not in seen:
            seen.add(combined)
            texts.append(combined)
    return texts


# ── IM entity parsing ─────────────────────────────────────────────────────────

# Matches: tableName( 中文描述 )  or  tableName（中文）
_ENTITY_HEADER_RE = re.compile(
    r'^([a-zA-Z][a-zA-Z0-9_]{1,})\s*[（(]\s*([\u4e00-\u9fff][^)）\n]{1,60}?)\s*[)）]'
)
# Field line: starts with PK, FK, or contains multiple EN identifiers
_FIELD_LINE_RE = re.compile(r'\b(PK|FK)\b|\b[a-zA-Z][a-zA-Z0-9_]{3,}\b')
# Extract individual EN field names (camelCase, lowercase, or PascalCase)
_FIELD_NAMES_RE = re.compile(r'\b[a-zA-Z][a-zA-Z0-9_]{2,}\b')


def _parse_im_entities(texts: list[str]) -> list[dict[str, Any]]:
    """
    Identify entity definitions from IM diagram text lines.

    Returns list of:
      {name, zh_name, attributes: [str], raw_text}
    """
    entities: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for text in texts:
        m = _ENTITY_HEADER_RE.match(text)
        if m:
            # Save previous entity
            if current:
                entities.append(current)
            current = {
                "name": m.group(1),
                "zh_name": m.group(2).strip(),
                "attributes": [],
                "raw_text": text,
            }
        elif current and _FIELD_LINE_RE.search(text):
            # Accumulate attribute names from this field-line text
            attrs = _FIELD_NAMES_RE.findall(text)
            # Filter out common noise
            skip = {"PK", "FK", "null", "true", "false", "new", "for", "from"}
            current["attributes"].extend(a for a in attrs if a not in skip and a not in current["attributes"])
            current["raw_text"] = current["raw_text"] + "\n" + text
        # else: unrelated label (swimlane titles, annotations) — skip

    if current:
        entities.append(current)
    return entities


# ── Tag assembly ──────────────────────────────────────────────────────────────

def _build_tags(texts: list[str], entities: list[dict], diagram_type: str) -> list[str]:
    """Assemble searchable tags from extracted text and parsed entities.

    Strategy:
    - IM diagrams: entity names (table names) + entity zh_names + selected CJK keywords
    - Flowcharts: CJK keywords from step text
    - EN identifiers: entity names only (not all attribute names — too many)
    """
    tags: set[str] = {diagram_type}

    # Entity names (table names) and their Chinese descriptions — always include
    for ent in entities:
        tags.add(ent["name"])
        zh = ent.get("zh_name", "")
        if zh:
            # Only take the first 4 CJK chars to avoid overly specific phrases
            tags.add(zh.strip()[:6])

    # CJK 2-4 char keywords from texts — limit to avoid flooding
    cjk_freq: dict[str, int] = {}
    for text in texts:
        for m in re.finditer(r'[\u4e00-\u9fff]{2,4}', text):
            tok = m.group(0)
            cjk_freq[tok] = cjk_freq.get(tok, 0) + 1
    # Only keep CJK keywords that appear at least twice (more signal, less noise)
    for tok, freq in cjk_freq.items():
        if freq >= 2:
            tags.add(tok)

    return sanitize_tags(sorted(tags))


# ── Diagram type detection ────────────────────────────────────────────────────

def _detect_diagram_type(source_file: str) -> str:
    stem = Path(source_file).stem.lower()
    if "im" in stem or "information" in stem or "model" in stem:
        return "vsd-im-diagram"
    return "vsd-flowchart"


# ── Record builder ────────────────────────────────────────────────────────────

def build_vsd_record(
    vsd_path: Path,
    svg_path: Path,
) -> dict[str, Any]:
    """Build a spec_docs-compatible record from a VSD + its SVG conversion."""
    texts = _extract_svg_texts(svg_path)
    diagram_type = _detect_diagram_type(vsd_path.name)

    if diagram_type == "vsd-im-diagram":
        entities = _parse_im_entities(texts)
    else:
        entities = []

    table_names = [e["name"] for e in entities]

    # Build content text for semantic search
    content_parts: list[str] = list(texts)
    if entities:
        for ent in entities:
            content_parts.append(f"{ent['name']} {ent.get('zh_name', '')}: {' '.join(ent['attributes'])}")
    content_text = "\n".join(content_parts)

    # Summary
    if entities:
        summary = f"資訊模型圖，包含 {len(entities)} 個實體/資料表：" + "、".join(table_names[:8])
        if len(table_names) > 8:
            summary += f" 等共 {len(table_names)} 個"
    else:
        summary = f"流程圖，共 {len(texts)} 個流程節點"

    # doc_id  vsd-<stem>
    stem_slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_-]', '-', vsd_path.stem).strip('-')
    doc_id = f"vsd-{stem_slug}"

    tags = _build_tags(texts, entities, diagram_type)

    now = utc_now_iso()
    return {
        "doc_id": doc_id,
        "title": vsd_path.stem,
        "doc_type": diagram_type,
        "source_file": vsd_path.name,
        "relative_path": str(vsd_path),
        "summary": summary,
        "content": content_text,
        # VSD-specific fields
        "all_texts": texts,
        "vsd_entities": entities,
        "table_names": table_names,
        "flow_steps": texts if diagram_type == "vsd-flowchart" else [],
        # KB metadata
        "tags": tags,
        "knowledge_scope": "spec",
        "source": "vsd-import",
        "created_at": now,
        "updated_at": now,
    }


# ── LibreOffice conversion ────────────────────────────────────────────────────

def convert_vsd_to_svg(vsd_path: Path, out_dir: Path) -> Path | None:
    """
    Convert VSD → SVG using LibreOffice soffice --headless.
    Returns the output SVG path, or None if conversion failed.
    """
    lo = _find_libreoffice()
    if not lo:
        raise RuntimeError("LibreOffice not found. Install it first (winget install TheDocumentFoundation.LibreOffice).")

    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [lo, "--headless", "--convert-to", "svg", "--outdir", str(out_dir), str(vsd_path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    svg_path = out_dir / (vsd_path.stem + ".svg")
    if svg_path.exists():
        return svg_path
    # LibreOffice sometimes returns exit 0 but still fails (e.g. format not supported)
    return None


# ── Main entry point ──────────────────────────────────────────────────────────

def ingest_vsd_files(
    paths: list[Path],
    db: Database,
    apply: bool = True,
) -> dict[str, Any]:
    """
    Ingest one or more VSD files into spec_docs.

    Returns a report dict with inserted/updated/failed counts.
    """
    report: dict[str, Any] = {
        "total": len(paths),
        "inserted": 0,
        "updated": 0,
        "failed": [],
    }

    with tempfile.TemporaryDirectory(prefix="kb_vsd_") as tmp:
        out_dir = Path(tmp)
        for vsd_path in paths:
            vsd_path = Path(vsd_path)
            if not vsd_path.exists():
                report["failed"].append({"file": str(vsd_path), "error": "file not found"})
                continue

            try:
                svg_path = convert_vsd_to_svg(vsd_path, out_dir)
                if not svg_path:
                    report["failed"].append({"file": str(vsd_path), "error": "LibreOffice SVG conversion produced no output"})
                    continue

                rec = build_vsd_record(vsd_path, svg_path)

                if not apply:
                    report.setdefault("dry_run", []).append({
                        "doc_id": rec["doc_id"],
                        "title": rec["title"],
                        "diagram_type": rec["doc_type"],
                        "entities": len(rec.get("vsd_entities", [])),
                        "texts": len(rec.get("all_texts", [])),
                        "tags": len(rec.get("tags", [])),
                    })
                    continue

                is_new = db["spec_docs"].find_one({"doc_id": rec["doc_id"]}) is None
                upsert_versioned(db, "spec_docs", "doc_id", rec["doc_id"], rec)
                action = "inserted" if is_new else "updated"
                if action == "inserted":
                    report["inserted"] += 1
                else:
                    report["updated"] += 1
                report.setdefault("records", []).append({
                    "doc_id": rec["doc_id"],
                    "action": action,
                    "diagram_type": rec["doc_type"],
                    "entities": len(rec.get("vsd_entities", [])),
                    "table_names": rec.get("table_names", [])[:10],
                    "texts": len(rec.get("all_texts", [])),
                })
            except Exception as exc:
                report["failed"].append({"file": str(vsd_path), "error": str(exc)})


# ── PPT / PPTX presentation ingestion ────────────────────────────────────────

def build_ppt_record(
    ppt_path: Path,
    svg_path: Path,
) -> dict[str, Any]:
    """Build a spec_docs-compatible record from a PPT/PPTX + its SVG conversion."""
    texts = _extract_svg_texts(svg_path)

    # Filter out placeholder texts common in Impress template exports
    _noise = {"<日期/時間>", "<頁尾>", "<編號>"}
    texts = [t for t in texts if t not in _noise]

    # Content text for semantic search
    content_text = "\n".join(texts)

    # Summary: use first meaningful text as title, count slides
    title_line = next((t for t in texts if len(t) > 3 and not t.startswith("<")), ppt_path.stem)
    summary = f"簡報文件，共 {len(texts)} 個文字區塊。主題：{title_line[:60]}"

    # doc_id  ppt-<stem>
    stem_slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_-]', '-', ppt_path.stem).strip('-')
    doc_id = f"ppt-{stem_slug}"

    # Tags: CJK freq-2+ keywords + first-line title tokens
    tags: set[str] = {"ppt-presentation"}
    cjk_freq: dict[str, int] = {}
    for text in texts:
        for m in re.finditer(r'[\u4e00-\u9fff]{2,4}', text):
            tok = m.group(0)
            cjk_freq[tok] = cjk_freq.get(tok, 0) + 1
    for tok, freq in cjk_freq.items():
        if freq >= 2:
            tags.add(tok)
    # EN identifiers (camelCase table names etc., min 4 chars, appearing 2+ times)
    en_freq: dict[str, int] = {}
    for text in texts:
        for m in re.finditer(r'\b[a-zA-Z][a-zA-Z0-9_]{3,}\b', text):
            tok = m.group(0)
            en_freq[tok] = en_freq.get(tok, 0) + 1
    _en_skip = {"null", "true", "false", "data", "date", "time", "type", "code", "name", "note", "flag"}
    for tok, freq in en_freq.items():
        if freq >= 2 and tok.lower() not in _en_skip:
            tags.add(tok)

    now = utc_now_iso()
    return {
        "doc_id": doc_id,
        "title": ppt_path.stem,
        "doc_type": "ppt-presentation",
        "source_file": ppt_path.name,
        "relative_path": str(ppt_path),
        "summary": summary,
        "content": content_text,
        "all_texts": texts,
        "tags": sanitize_tags(sorted(tags)),
        "knowledge_scope": "spec",
        "source": "ppt-import",
        "created_at": now,
        "updated_at": now,
    }


def ingest_ppt_files(
    paths: list[Path],
    db: Database,
    apply: bool = True,
) -> dict[str, Any]:
    """
    Ingest one or more PPT/PPTX files into spec_docs via LibreOffice SVG conversion.

    Returns a report dict with inserted/updated/failed counts.
    """
    report: dict[str, Any] = {
        "total": len(paths),
        "inserted": 0,
        "updated": 0,
        "failed": [],
    }

    with tempfile.TemporaryDirectory(prefix="kb_ppt_") as tmp:
        out_dir = Path(tmp)
        for ppt_path in paths:
            ppt_path = Path(ppt_path)
            if not ppt_path.exists():
                report["failed"].append({"file": str(ppt_path), "error": "file not found"})
                continue

            try:
                # Reuse the same LibreOffice SVG conversion pipeline
                svg_path = convert_vsd_to_svg(ppt_path, out_dir)
                if not svg_path:
                    report["failed"].append({"file": str(ppt_path), "error": "LibreOffice SVG conversion produced no output"})
                    continue

                rec = build_ppt_record(ppt_path, svg_path)

                if not apply:
                    report.setdefault("dry_run", []).append({
                        "doc_id": rec["doc_id"],
                        "title": rec["title"],
                        "texts": len(rec.get("all_texts", [])),
                        "tags": len(rec.get("tags", [])),
                        "summary": rec["summary"],
                    })
                    continue

                is_new = db["spec_docs"].find_one({"doc_id": rec["doc_id"]}) is None
                upsert_versioned(db, "spec_docs", "doc_id", rec["doc_id"], rec)
                action = "inserted" if is_new else "updated"
                if action == "inserted":
                    report["inserted"] += 1
                else:
                    report["updated"] += 1
                report.setdefault("records", []).append({
                    "doc_id": rec["doc_id"],
                    "action": action,
                    "texts": len(rec.get("all_texts", [])),
                    "content_len": len(rec.get("content", "")),
                    "tags": len(rec.get("tags", [])),
                })
            except Exception as exc:
                report["failed"].append({"file": str(ppt_path), "error": str(exc)})

    return report
