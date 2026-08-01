"""
knowledge_base/ui_screen_ingest.py
-----------------------------------
Ingest UI screen walkthrough DOCX files into the `ui_screens` MongoDB collection.

Each DOCX contains a sequence of paragraphs where each paragraph is one step:
  TEXT (description)  +  optional embedded screenshot (image)

Extraction pipeline per file:
  1. Parse DOCX paragraphs → steps (description + image bytes)
  2. Save screenshots as PNG under vault/ui_screens/<scenario>/step_NN.png
  3. Extract UI element/field names from step descriptions (regex)
  4. OCR each screenshot with Windows.Media.Ocr (繁中, fallback: skip)
  5. Augment ui_elements with OCR-extracted field names
  6. Upsert record into `ui_screens` collection
"""
from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from pymongo.database import Database

from knowledge_base.config import load_settings
from knowledge_base.documents import utc_now_iso, upsert_versioned


# ─────────────────────────────────────────
# UI element extraction from text
# ─────────────────────────────────────────

_BRACKET_RE = re.compile(r"\[([^\[\]]{1,40})\]|【([^【】]{1,40})】|〔([^〔〕]{1,40})〕")
_ACTION_RE = re.compile(r"(?:選擇|輸入|確認|點選)([^，。\n（(\[【]{1,60})")
_SPLIT_RE = re.compile(r"[、，,]")


def _extract_ui_elements(text: str) -> list[str]:
    """Return UI field/button names found in a step description string."""
    found: list[str] = []
    for m in _BRACKET_RE.finditer(text):
        val = next(g for g in m.groups() if g)
        found.append(val.strip())
    for m in _ACTION_RE.finditer(text):
        parts = _SPLIT_RE.split(m.group(1))
        found.extend(p.strip() for p in parts if len(p.strip()) >= 2)
    seen: set[str] = set()
    result: list[str] = []
    for f in found:
        f = f.strip()
        if f and f not in seen:
            seen.add(f)
            result.append(f)
    return result


# ─────────────────────────────────────────
# Windows OCR (繁中)
# ─────────────────────────────────────────

_OCR_AVAILABLE: bool | None = None


def _ocr_available() -> bool:
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is not None:
        return _OCR_AVAILABLE
    try:
        import winsdk.windows.media.ocr as _  # noqa: F401
        _OCR_AVAILABLE = True
    except ImportError:
        _OCR_AVAILABLE = False
    return _OCR_AVAILABLE


async def _do_ocr_async(image_bytes: bytes) -> str:
    import winsdk.windows.media.ocr as wocr
    import winsdk.windows.graphics.imaging as wgi
    import winsdk.windows.storage.streams as wss

    stream = wss.InMemoryRandomAccessStream()
    writer = wss.DataWriter(stream)
    writer.write_bytes(image_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await wgi.BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    # Prefer zh-Hant; fall back to user profile
    try:
        import winsdk.windows.globalization as wglob
        lang = wglob.Language("zh-Hant")
        engine = wocr.OcrEngine.try_create_from_language(lang)
    except Exception:
        engine = None
    if engine is None:
        engine = wocr.OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return ""

    result = await engine.recognize_async(bitmap)
    return result.text if result else ""


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Run Windows OCR on raw image bytes. Returns empty string on failure."""
    if not _ocr_available():
        return ""
    try:
        loop = asyncio.new_event_loop()
        text = loop.run_until_complete(_do_ocr_async(image_bytes))
        loop.close()
        return text or ""
    except Exception:
        return ""


# ─────────────────────────────────────────
# Scenario / ID helpers
# ─────────────────────────────────────────

_UUID_PREFIX_RE = re.compile(r"^[0-9a-f\-]{20,}-")


def _derive_scenario(docx_path: Path) -> str:
    """Derive scenario name from DOCX filename.

    Examples:
      99469a02-c828-...-新架構優惠方案異動_作業畫面.docx → 新架構優惠方案異動
      新架構優惠方案異動_作業畫面.docx                   → 新架構優惠方案異動
    """
    stem = docx_path.stem
    stem = _UUID_PREFIX_RE.sub("", stem)
    stem = stem.removesuffix("_作業畫面")
    return stem.strip()


def _screen_id(scenario: str) -> str:
    safe = re.sub(r'[\s/\\:*?"<>|]', "-", scenario)
    return f"ui-{safe}"


# ─────────────────────────────────────────
# DOCX → steps + screenshots
# ─────────────────────────────────────────

def _save_image(image_bytes: bytes, dest: Path) -> None:
    """Save image bytes as PNG (convert format if PIL available)."""
    try:
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(image_bytes))
        img.save(str(dest), "PNG")
    except Exception:
        dest.write_bytes(image_bytes)


def parse_ui_screen_docx(
    docx_path: Path,
    vault_path: Path,
    do_ocr: bool = True,
) -> dict[str, Any]:
    """Parse one UI walkthrough DOCX and return an unsaved ui_screens record."""
    doc = Document(str(docx_path))
    rels = doc.part.rels
    scenario = _derive_scenario(docx_path)
    img_dir = vault_path / "ui_screens" / scenario
    img_dir.mkdir(parents=True, exist_ok=True)

    steps: list[dict[str, Any]] = []
    all_ui_fields: list[str] = []
    img_counter = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        blips = para._element.findall(".//" + qn("a:blip"))

        if not text and not blips:
            continue

        step: dict[str, Any] = {
            "seq": len(steps) + 1,
            "description": text,
            "ui_elements": _extract_ui_elements(text),
            "has_screenshot": bool(blips),
            "screenshot_rel_path": None,
            "ocr_text": "",
        }

        if blips:
            img_counter += 1
            r_id = blips[0].get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )
            if r_id and r_id in rels:
                image_bytes: bytes = rels[r_id].target_part.blob
                img_name = f"step_{img_counter:02d}.png"
                img_path = img_dir / img_name
                _save_image(image_bytes, img_path)
                step["screenshot_rel_path"] = f"ui_screens/{scenario}/{img_name}"

                if do_ocr:
                    ocr_text = ocr_image_bytes(image_bytes)
                    step["ocr_text"] = ocr_text
                    if ocr_text:
                        for field in _extract_ui_elements(ocr_text):
                            if field not in step["ui_elements"]:
                                step["ui_elements"].append(field)

        for field in step["ui_elements"]:
            if field not in all_ui_fields:
                all_ui_fields.append(field)
        steps.append(step)

    # Build summary and tags
    descriptions = [s["description"] for s in steps if s["description"]]
    flow_text = " → ".join(descriptions)
    summary = f"{scenario} 操作流程：{flow_text[:250]}"

    tags: list[str] = list({scenario} | {
        f for f in all_ui_fields if len(f) >= 2
    })
    for kw in ("優惠", "購機", "促銷", "確認", "受理", "異動"):
        if kw in flow_text and kw not in tags:
            tags.append(kw)

    return {
        "screen_id": _screen_id(scenario),
        "scenario": scenario,
        "title": f"{scenario} 作業畫面",
        "source_file": docx_path.name,
        "steps": steps,
        "all_ui_fields": all_ui_fields,
        "summary": summary,
        "tags": tags,
        "knowledge_scope": "spec",
        "ocr_available": _ocr_available(),
    }


# ─────────────────────────────────────────
# Public ingest entry point
# ─────────────────────────────────────────

def ingest_ui_screens(
    db: Database,
    source_paths: list[Path],
    do_ocr: bool = True,
) -> dict[str, Any]:
    """Ingest one or more UI screen DOCX files into `ui_screens` collection."""
    settings = load_settings()
    vault_path = settings.vault_path
    counts: dict[str, Any] = {"seen": 0, "inserted": 0, "updated": 0, "errors": 0}
    errors: list[str] = []

    for path in source_paths:
        counts["seen"] += 1
        try:
            record = parse_ui_screen_docx(path, vault_path, do_ocr=do_ocr)
            existing = db["ui_screens"].find_one({"screen_id": record["screen_id"]})
            upsert_versioned(db, "ui_screens", "screen_id", record["screen_id"], record)
            if existing is None:
                counts["inserted"] += 1
            else:
                counts["updated"] += 1
        except Exception as exc:
            counts["errors"] += 1
            errors.append(f"{path.name}: {exc}")

    if errors:
        counts["errors_detail"] = errors
    return counts
