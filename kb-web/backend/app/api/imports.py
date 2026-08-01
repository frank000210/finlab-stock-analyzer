import ipaddress
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import trafilatura
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from pymongo.database import Database

from ..deps import get_db, require_auth
from knowledge_base.spec_ingest import ingest_spec_documents
from knowledge_base.semantic_search import rebuild_semantic_index

router = APIRouter(prefix="/api", tags=["imports"])

ALLOWED_SUFFIXES = {".docx", ".pptx", ".pdf", ".md", ".txt"}
LEGACY_SUFFIXES = {".doc", ".ppt"}
# NN4: bound worst-case memory/disk from a single upload. Comfortably above
# any real spec document; just a backstop against mistaken/oversized files.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("/import/file")
async def import_file(
    file: UploadFile = File(...),
    domain: str = Form(...),
    db: Database = Depends(get_db),
    _: str = Depends(require_auth),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix in LEGACY_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{suffix} 需要 LibreOffice 轉檔，網頁不支援直接上傳。"
                "請改用本機 CLI（見 F:\\knowledge_base\\knowledge-base-setup-guide.md）。"
            ),
        )
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"不支援的檔案格式：{suffix}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"檔案過大（上限 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB）。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / file.filename
        tmp_path.write_bytes(content)
        result = ingest_spec_documents(
            db=db,
            root_path=Path(tmp),
            forced_doc_type=domain,
            content_only=True,
        )
    rebuild_semantic_index(db, collections=["spec_docs"], force=False)
    return result


class UrlImportPayload(BaseModel):
    url: str
    domain: str


def _assert_public_url(url: str) -> None:
    # NN10: /api/import/url makes the server fetch an arbitrary
    # caller-supplied URL. Without this, a logged-in caller could point it
    # at localhost, RFC1918 ranges, or a cloud metadata endpoint (SSRF) --
    # this server also runs other internal services on the same host.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="只允許 http/https 網址。")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="網址格式不正確。")
    try:
        resolved_ips = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail=f"無法解析網址主機：{hostname}") from exc
    for ip_str in resolved_ips:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(status_code=422, detail="不允許抓取內網或本機位址。")


@router.post("/import/url")
def import_url(
    payload: UrlImportPayload,
    db: Database = Depends(get_db),
    _: str = Depends(require_auth),
):
    _assert_public_url(payload.url)

    try:
        resp = requests.get(payload.url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=422, detail=f"抓取網頁失敗：{exc}") from exc

    extracted = trafilatura.extract(resp.text, include_comments=False, favor_recall=True)
    if not extracted or len(extracted.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="抓不到有意義的正文，可能是需要 JavaScript 才能顯示內容的動態網站。",
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "web-import.md"
        tmp_path.write_text(f"<!-- source_url: {payload.url} -->\n\n{extracted}", encoding="utf-8")
        result = ingest_spec_documents(
            db=db,
            root_path=Path(tmp),
            forced_doc_type=payload.domain,
            content_only=True,
        )
    for doc_id in result.get("doc_ids", []):
        db.spec_docs.update_one({"doc_id": doc_id}, {"$set": {"source_url": payload.url}})
    rebuild_semantic_index(db, collections=["spec_docs"], force=False)
    return result
