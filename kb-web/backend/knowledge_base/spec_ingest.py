from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from typing import Any

from pymongo.database import Database

from knowledge_base.documents import upsert_versioned
from knowledge_base.vault_clean import sanitize_tags

SUPPORTED_EXTENSIONS = {
    ".md",
    ".txt",
    ".rst",
    ".doc",
    ".docx",
    ".java",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".vsd",
}
DOCX_SIGNATURE = b"PK"
HISTORY_HEADING_PATTERNS = [
    re.compile(r"^\s*(修訂紀錄|版本沿革|文件修改歷程|異動紀錄|revision\s*history|change\s*log)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(版次|版本|修訂|變更)\s*(紀錄|歷程)?\s*$", re.IGNORECASE),
]
BODY_HEADING_PATTERNS = [
    re.compile(r"^\s*第\s*[一二三四五六七八九十百零0-9]+\s*章"),
    re.compile(r"^\s*[一二三四五六七八九十]+\s*[、.．]\s*\S+"),
    re.compile(r"^\s*\d+(?:\.\d+){0,3}\s+\S+"),
    re.compile(r"^\s*\d+\s*[、.．]\s*\S+"),
]
UI_PAGE_PATTERNS = [
    re.compile(r"^\s*畫面\s*\d+\s*[:：]?\s*(.+)?$"),
    re.compile(r"^\s*screen\s*\d+\s*[:：]?\s*(.+)?$", re.IGNORECASE),
    re.compile(r"^\s*頁面\s*\d+\s*[:：]?\s*(.+)?$"),
]
UI_FLOW_SECTION_PATTERNS = [
    re.compile(r"(流程|操作劇本|usecase|情境)", re.IGNORECASE),
]
EN_FIELD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.]{2,}")
ZH_EN_PAIR_PATTERN = re.compile(
    r"(?P<zh>[\u4e00-\u9fffA-Za-z0-9／、\-\s]{2,60})\((?P<en>[A-Za-z][A-Za-z0-9_.]{2,})\)"
)
UI_CONTROL_HINTS: dict[str, tuple[str, ...]] = {
    "textbox": ("輸入", "欄位", "帳號", "代碼", "證號", "號碼", "email", "imei"),
    "dropdown": ("下拉", "選擇", "選單"),
    "checkbox": ("勾選", "核取", "checkbox"),
    "radio": ("radio", "單選"),
    "button": ("按鈕", "送出", "查詢", "確定", "取消"),
    "table": ("清單", "列表", "table", "grid"),
}


def _slugify(text: str) -> str:
    lowered = text.lower().strip().replace("\\", "/")
    slug = re.sub(r"[^a-z0-9/_-]+", "-", lowered)
    return slug.strip("-").replace("/", "__")


def _summarize(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return "spec document"


def _extract_text_tags(text: str, max_terms: int = 30) -> list[str]:
    words = re.findall(r"[a-z0-9_]{3,}", text.lower())
    unique: list[str] = []
    seen: set[str] = set()
    for word in words:
        if word in seen:
            continue
        seen.add(word)
        unique.append(word)
        if len(unique) >= max_terms:
            break
    return unique


def _detect_doc_type(path: Path) -> str:
    lowered = str(path).lower()
    if "srs" in lowered:
        return "srs"
    if "sds" in lowered:
        return "sds"
    if "prd" in lowered:
        return "prd"
    if "adr" in lowered:
        return "adr"
    return "spec"


def _safe_read_text(path: Path) -> str | None:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "cp950", "big5", "latin1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return None


def _extract_binary_strings(path: Path, min_len: int = 4) -> str:
    raw = path.read_bytes()
    latin = raw.decode("latin1", errors="ignore")
    ascii_chunks = re.findall(r"[A-Za-z0-9_\-\.\:/\u4e00-\u9fff]{%d,}" % min_len, latin)
    utf16_chunks: list[str] = []
    try:
        utf16 = raw.decode("utf-16-le", errors="ignore")
        utf16_chunks = re.findall(r"[A-Za-z0-9_\-\.\:/\u4e00-\u9fff]{%d,}" % min_len, utf16)
    except UnicodeDecodeError:
        pass
    combined = list(dict.fromkeys(ascii_chunks + utf16_chunks))
    return "\n".join(combined[:3000]).strip()


def _is_openxml_docx(path: Path) -> bool:
    if path.suffix.lower() != ".docx":
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(2) == DOCX_SIGNATURE
    except OSError:
        return False


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", " ", xml)
    xml = re.sub(r"\n{3,}", "\n\n", xml)
    xml = re.sub(r"[ \t]{2,}", " ", xml)
    return xml.strip()


def _extract_pptx_text(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path, "r") as archive:
        slide_names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
        for slide_name in slide_names:
            xml = archive.read(slide_name).decode("utf-8", errors="ignore")
            xml = re.sub(r"</a:p>", "\n", xml)
            xml = re.sub(r"<[^>]+>", " ", xml)
            xml = re.sub(r"[ \t]{2,}", " ", xml)
            texts.append(xml.strip())
    return "\n\n".join(chunk for chunk in texts if chunk).strip()


def _extract_xlsx_text(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path, "r") as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_xml = archive.read("xl/sharedStrings.xml").decode("utf-8", errors="ignore")
            root = ElementTree.fromstring(shared_xml)
            for node in root.iter():
                if node.tag.endswith("}t") and node.text:
                    shared_strings.append(node.text.strip())

        sheet_names = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        for sheet_name in sheet_names:
            xml = archive.read(sheet_name).decode("utf-8", errors="ignore")
            root = ElementTree.fromstring(xml)
            sheet_lines: list[str] = []
            for cell in root.iter():
                if not cell.tag.endswith("}c"):
                    continue
                cell_type = cell.attrib.get("t")
                value_node = next((child for child in list(cell) if child.tag.endswith("}v")), None)
                if value_node is None or value_node.text is None:
                    continue
                value = value_node.text.strip()
                if cell_type == "s":
                    if value.isdigit() and int(value) < len(shared_strings):
                        value = shared_strings[int(value)]
                sheet_lines.append(value)
            if sheet_lines:
                texts.append("\n".join(sheet_lines))
    return "\n\n".join(texts).strip()


def _extract_excel_com(path: Path) -> str:
    try:
        import win32com.client  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pywin32 is required to ingest Excel binary files on Windows.") from exc
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    workbook = None
    try:
        workbook = excel.Workbooks.Open(str(path), ReadOnly=True)
        lines: list[str] = []
        for sheet in workbook.Worksheets:
            lines.append(f"[Sheet] {sheet.Name}")
            used = sheet.UsedRange
            if used is None:
                continue
            values = used.Value
            if values is None:
                continue
            if isinstance(values, tuple):
                for row in values:
                    if isinstance(row, tuple):
                        row_text = " | ".join(str(cell).strip() for cell in row if cell is not None and str(cell).strip())
                        if row_text:
                            lines.append(row_text)
                    elif row is not None and str(row).strip():
                        lines.append(str(row).strip())
            elif str(values).strip():
                lines.append(str(values).strip())
        return "\n".join(lines).strip()
    finally:
        if workbook is not None:
            workbook.Close(False)
        excel.Quit()


def _extract_powerpoint_com(path: Path) -> str:
    try:
        import win32com.client  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pywin32 is required to ingest PowerPoint binary files on Windows.") from exc
    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = True
    presentation = None
    try:
        presentation = app.Presentations.Open(str(path), WithWindow=False)
        lines: list[str] = []
        for slide in presentation.Slides:
            lines.append(f"[Slide] {slide.SlideIndex}")
            for shape in slide.Shapes:
                if shape.HasTextFrame and shape.TextFrame.HasText:
                    text = str(shape.TextFrame.TextRange.Text).strip()
                    if text:
                        lines.append(text)
        return "\n".join(lines).strip()
    finally:
        if presentation is not None:
            presentation.Close()
        app.Quit()


def _extract_visio_com(path: Path) -> str:
    try:
        import win32com.client  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pywin32 is required to ingest Visio files on Windows.") from exc
    visio = win32com.client.DispatchEx("Visio.Application")
    visio.Visible = False
    document = None
    try:
        document = visio.Documents.Open(str(path))
        lines: list[str] = []
        for page in document.Pages:
            lines.append(f"[Page] {page.Name}")
            for shape in page.Shapes:
                text = str(shape.Text).strip()
                if text:
                    lines.append(text)
        return "\n".join(lines).strip()
    finally:
        if document is not None:
            document.Close()
        visio.Quit()


def _clean_word_text(text: str) -> str:
    text = text.replace("\x07", " ").replace("\x0b", " ").replace("\x0c", " ").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _is_history_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in HISTORY_HEADING_PATTERNS)


def _is_body_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in BODY_HEADING_PATTERNS)


def _trim_to_main_content(content: str) -> tuple[str, bool]:
    lines = content.splitlines()
    history_idx: int | None = None
    body_idx: int | None = None

    for idx, raw in enumerate(lines[:220]):
        line = raw.strip()
        if not line:
            continue
        if history_idx is None and _is_history_heading(line):
            history_idx = idx
        if body_idx is None and _is_body_heading(line):
            body_idx = idx
        if history_idx is not None and body_idx is not None:
            break

    if history_idx is None or body_idx is None or body_idx <= history_idx:
        return content, False
    trimmed = "\n".join(lines[body_idx:]).strip()
    if not trimmed:
        return content, False
    return trimmed, True


def _extract_with_word_com(path: Path) -> str:
    try:
        import win32com.client  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pywin32 is required to ingest legacy Word files on Windows.") from exc

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        document = word.Documents.Open(str(path), False, True)
        raw = str(document.Content.Text)
        document.Close(False)
    finally:
        try:
            word.Quit()
        except Exception:
            pass
    return _clean_word_text(raw)


def _extract_content(path: Path) -> tuple[str | None, str]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".rst", ".java"}:
        return _safe_read_text(path), "text-read"
    if suffix == ".pptx":
        try:
            return _extract_pptx_text(path), "pptx-xml"
        except (OSError, ValueError, ElementTree.ParseError, zipfile.BadZipFile):
            pass
        try:
            return _extract_powerpoint_com(path), "ppt-content-text"
        except Exception:
            binary = _extract_binary_strings(path)
            return (binary if binary else None), "pptx-binary-strings"
    if suffix == ".xlsx":
        try:
            return _extract_xlsx_text(path), "xlsx-xml"
        except (OSError, ValueError, ElementTree.ParseError, zipfile.BadZipFile):
            pass
        try:
            return _extract_excel_com(path), "xlsx-content-text"
        except Exception:
            binary = _extract_binary_strings(path)
            return (binary if binary else None), "xlsx-binary-strings"
    if suffix == ".docx" and _is_openxml_docx(path):
        try:
            return _extract_docx_text(path), "docx-xml"
        except Exception:
            # fallback to Word COM for damaged xml packages
            pass
    if suffix in {".doc", ".docx"}:
        try:
            return _extract_with_word_com(path), "word-content-text"
        except Exception:
            return None, "word-content-text-failed"
    if suffix == ".ppt":
        try:
            return _extract_powerpoint_com(path), "ppt-content-text"
        except Exception:
            binary = _extract_binary_strings(path)
            return (binary if binary else None), "ppt-binary-strings"
    if suffix == ".xls":
        try:
            return _extract_excel_com(path), "xls-content-text"
        except Exception:
            binary = _extract_binary_strings(path)
            return (binary if binary else None), "xls-binary-strings"
    if suffix == ".vsd":
        try:
            return _extract_visio_com(path), "vsd-content-text"
        except Exception:
            binary = _extract_binary_strings(path)
            return (binary if binary else None), "vsd-binary-strings"
    return None, "unsupported"


def _quality_metrics(content: str, title: str) -> dict[str, Any]:
    length = len(content)
    if length == 0:
        return {
            "len": 0,
            "cjk_ratio": 0.0,
            "latin_ratio": 0.0,
            "symbol_ratio": 1.0,
            "title_hit": False,
            "pass": False,
        }
    cjk = len(re.findall(r"[\u4e00-\u9fff]", content))
    latin = len(re.findall(r"[A-Za-z0-9]", content))
    symbols = max(0, length - cjk - latin)
    cjk_ratio = cjk / length
    latin_ratio = latin / length
    symbol_ratio = symbols / length
    title_tokens = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,}", title)
    title_hit = any(token in content for token in title_tokens[:8]) if title_tokens else False
    quality_pass = (
        length >= 1200
        and (cjk_ratio + latin_ratio) >= 0.45
        and symbol_ratio <= 0.55
        and title_hit
    )
    return {
        "len": length,
        "cjk_ratio": round(cjk_ratio, 4),
        "latin_ratio": round(latin_ratio, 4),
        "symbol_ratio": round(symbol_ratio, 4),
        "title_hit": title_hit,
        "pass": quality_pass,
    }


def _infer_control_type(line: str) -> str:
    lowered = line.lower()
    for control, hints in UI_CONTROL_HINTS.items():
        if any(hint in lowered or hint in line for hint in hints):
            return control
    return "unknown"


def _extract_ui_knowledge(content: str, source_path: Path) -> dict[str, Any]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    pages: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    scenario_flows: list[dict[str, Any]] = []
    current_page = "default"
    current_scenario = "default"

    for idx, line in enumerate(lines, start=1):
        for pattern in UI_PAGE_PATTERNS:
            match = pattern.match(line)
            if match:
                page_name = match.group(1).strip() if match.group(1) else line
                current_page = f"p{len(pages) + 1}"
                pages.append(
                    {
                        "page_id": current_page,
                        "page_name": page_name or line,
                        "line_no": idx,
                        "source": "text",
                    }
                )
                break

        if any(pattern.search(line) for pattern in UI_FLOW_SECTION_PATTERNS):
            current_scenario = f"s{len({f['scenario_id'] for f in scenario_flows}) + 1}"
            scenario_flows.append(
                {
                    "scenario_id": current_scenario,
                    "step_no": 0,
                    "page_id": current_page,
                    "action": line[:200],
                    "trigger_condition": "",
                    "line_no": idx,
                    "confidence": 0.8,
                }
            )

        if re.match(r"^(Step\s*\d+|UseCase\d+(?:\.\d+)?|\d+-\d+)", line, re.IGNORECASE):
            scenario_flows.append(
                {
                    "scenario_id": current_scenario,
                    "step_no": len([x for x in scenario_flows if x["scenario_id"] == current_scenario]),
                    "page_id": current_page,
                    "action": line[:240],
                    "trigger_condition": "",
                    "line_no": idx,
                    "confidence": 0.75,
                }
            )

        pair_match = ZH_EN_PAIR_PATTERN.search(line)
        if pair_match:
            zh_label = pair_match.group("zh").strip()
            en_field = pair_match.group("en").strip()
            control_type = _infer_control_type(line)
            field_id = f"{current_page}-f{len(fields) + 1}"
            fields.append(
                {
                    "field_id": field_id,
                    "page_id": current_page,
                    "field_label_zh": zh_label,
                    "field_name_en": en_field,
                    "control_type": control_type,
                    "required": "必填" in line or "must" in line.lower(),
                    "editable": "唯讀" not in line and "readonly" not in line.lower(),
                    "validation_rule": line[:240],
                    "source_line": idx,
                    "confidence": 0.9,
                }
            )
            mappings.append(
                {
                    "mapping_id": f"m{len(mappings) + 1}",
                    "page_id": current_page,
                    "field_label_zh": zh_label,
                    "srs_field_en": en_field,
                    "match_type": "exact",
                    "source_line": idx,
                    "confidence": 0.9,
                }
            )
            continue

        if "欄位" in line or "輸入" in line or "輸出" in line:
            en_candidates = EN_FIELD_PATTERN.findall(line)
            if en_candidates:
                en_field = en_candidates[0]
                zh_label = line.split(en_field)[0].strip(" ：:()[]")[:60] or "unknown"
                field_id = f"{current_page}-f{len(fields) + 1}"
                fields.append(
                    {
                        "field_id": field_id,
                        "page_id": current_page,
                        "field_label_zh": zh_label,
                        "field_name_en": en_field,
                        "control_type": _infer_control_type(line),
                        "required": "必填" in line,
                        "editable": "唯讀" not in line and "readonly" not in line.lower(),
                        "validation_rule": line[:240],
                        "source_line": idx,
                        "confidence": 0.65,
                    }
                )
                mappings.append(
                    {
                        "mapping_id": f"m{len(mappings) + 1}",
                        "page_id": current_page,
                        "field_label_zh": zh_label,
                        "srs_field_en": en_field,
                        "match_type": "heuristic",
                        "source_line": idx,
                        "confidence": 0.65,
                    }
                )

    seen_fields: set[tuple[str, str, str]] = set()
    dedup_fields: list[dict[str, Any]] = []
    for field in fields:
        dedup_key = (
            field["page_id"],
            field["field_label_zh"].lower(),
            field["field_name_en"].lower(),
        )
        if dedup_key in seen_fields:
            continue
        seen_fields.add(dedup_key)
        dedup_fields.append(field)

    has_ui_figure = any("畫面" in line or "流程圖" in line or "diagram" in line.lower() for line in lines)
    contains_placeholder = any("\x01" in line for line in lines)
    needs_ui_review = (has_ui_figure and len(dedup_fields) < 3) or contains_placeholder

    return {
        "enabled": True,
        "pages": pages,
        "fields": dedup_fields,
        "field_mappings": mappings,
        "scenario_flows": scenario_flows,
        "has_ui_figure": has_ui_figure,
        "contains_placeholder": contains_placeholder,
        "needs_ui_review": needs_ui_review,
        "ocr_status": "pending_manual_or_optional_ocr" if contains_placeholder else "not_required",
        "source_path": str(source_path),
    }


def ingest_spec_documents(
    db: Database,
    root_path: Path,
    forced_doc_type: str | None = None,
    content_only: bool = True,
    batch_size: int = 50,
    max_files: int | None = None,
    strict_quality: bool = False,
    report_path: Path | None = None,
) -> dict[str, Any]:
    if not root_path.exists():
        raise ValueError(f"Path not found: {root_path}")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    files = sorted(
        [
            path
            for path in root_path.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not path.name.startswith("~$")
        ],
        key=lambda p: str(p).lower(),
    )
    if max_files is not None and max_files > 0:
        files = files[:max_files]

    imported = 0
    skipped = 0
    failed = 0
    quality_failed = 0
    preface_trimmed = 0
    ui_docs = 0
    ui_fields_count = 0
    ui_mapping_count = 0
    ui_flow_count = 0
    ui_review_needed = 0
    keys: list[str] = []
    failures: list[dict[str, str]] = []
    quality_failures: list[dict[str, Any]] = []

    for start in range(0, len(files), batch_size):
        batch = files[start : start + batch_size]
        for path in batch:
            content, converter = _extract_content(path)
            if content is None:
                failed += 1
                failures.append({"file": str(path), "error": converter})
                continue

            content = content.strip()
            if not content:
                skipped += 1
                continue

            if content_only:
                content, trimmed = _trim_to_main_content(content)
                if trimmed:
                    preface_trimmed += 1

            relative = path.relative_to(root_path)
            doc_type = forced_doc_type or _detect_doc_type(relative)
            digest = hashlib.sha1(str(relative).encode("utf-8")).hexdigest()[:10]
            doc_id = f"{doc_type}-{_slugify(str(relative.with_suffix('')))}-{digest}"
            title = relative.stem
            summary = _summarize(content)
            quality = _quality_metrics(content, title)
            ui_knowledge = _extract_ui_knowledge(content, path)
            if ui_knowledge["has_ui_figure"] or ui_knowledge["fields"] or ui_knowledge["scenario_flows"]:
                ui_docs += 1
                ui_fields_count += len(ui_knowledge["fields"])
                ui_mapping_count += len(ui_knowledge["field_mappings"])
                ui_flow_count += len(ui_knowledge["scenario_flows"])
                if ui_knowledge["needs_ui_review"]:
                    ui_review_needed += 1

            if not quality["pass"]:
                quality_failed += 1
                quality_failures.append({"file": str(path), **quality})
                if strict_quality:
                    skipped += 1
                    continue

            tags = sanitize_tags(
                {
                    "spec",
                    "document",
                    doc_type,
                    "knowledge_scope:spec",
                    *(
                        part.lower()
                        for part in relative.parts
                        if part and not part.startswith("~$")
                    ),
                    *_extract_text_tags(f"{title} {summary} {content[:1800]}"),
                }
            )

            upsert_versioned(
                db,
                "spec_docs",
                "doc_id",
                doc_id,
                {
                    "title": title,
                    "summary": summary,
                    "content": content,
                    "doc_type": doc_type,
                    "source_path": str(path),
                    "relative_path": str(relative).replace("/", "\\"),
                    "knowledge_scope": "spec",
                    "tags": tags,
                    "converter": converter,
                    "quality": quality,
                    "content_only": content_only,
                    "preface_trimmed": trimmed if content_only else False,
                    "ui_knowledge": ui_knowledge,
                },
            )
            upsert_versioned(
                db,
                "ui_knowledge",
                "ui_doc_id",
                doc_id,
                {
                    "doc_id": doc_id,
                    "title": title,
                    "doc_type": doc_type,
                    "source_path": str(path),
                    "relative_path": str(relative).replace("/", "\\"),
                    "knowledge_scope": "spec",
                    **ui_knowledge,
                },
            )
            imported += 1
            keys.append(doc_id)

    result: dict[str, Any] = {
        "root": str(root_path),
        "files_total": len(files),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "quality_failed": quality_failed,
        "content_only": content_only,
        "preface_trimmed": preface_trimmed,
        "ui_docs": ui_docs,
        "ui_fields": ui_fields_count,
        "ui_field_mappings": ui_mapping_count,
        "ui_scenario_flows": ui_flow_count,
        "ui_needs_review": ui_review_needed,
        "doc_ids": keys,
        "failures_preview": failures[:20],
        "quality_failures_preview": quality_failures[:20],
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["report_path"] = str(report_path)

    return result
