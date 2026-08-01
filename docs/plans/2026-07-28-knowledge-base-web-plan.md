# 知識庫網頁 Implementation Plan

**Goal:** Build a Vue + FastAPI web app (`kb-web/`) that lets Frank import documents/URLs into the `knowledge_base` MongoDB and ask questions answered by Claude, grounded in retrieved knowledge with citations; deploy it as a new Zeabur service in the `finlab-stock-analyzer` repo.
**Architecture:** Single FastAPI service serves both `/api/*` JSON routes and the built Vue SPA (same pattern as the existing repo-root `Dockerfile`). The backend vendors a copy of `F:\knowledge_base\knowledge_base` (the existing ingest/query/semantic-search package) into `kb-web/backend/knowledge_base/` and calls its functions directly — no shelling out to the CLI. Auth follows the existing house pattern in `backend/app/api/auth.py`: JWT bearer token returned in the login response body, sent back as `Authorization: Bearer <token>`. A second static secret (`KB_API_TOKEN`) is accepted on the same header for CLI/AI-tool callers.
**Tech Stack:** FastAPI, PyJWT, pymongo, `anthropic` SDK, `requests` + `trafilatura`; Vue 3 + Vite + Pinia + vue-router + axios (mirrors `frontend/package.json`).

Spec: [docs/08-知識庫網頁規格.md](../08-知識庫網頁規格.md)

---

## Task 0: Vendor the knowledge_base package into the repo

**Files:**
- Create: `kb-web/backend/knowledge_base/` (copy of `F:\knowledge_base\knowledge_base\*.py`)

**Steps:**
1. Copy the package (Windows `robocopy`, excluding `__pycache__`):
   ```powershell
   robocopy "F:\knowledge_base\knowledge_base" "F:\github\finlab-stock-analyzer\kb-web\backend\knowledge_base" *.py /XD __pycache__
   ```
2. Verify the copy has the same file count as the source (18 `.py` files):
   ```powershell
   (Get-ChildItem F:\knowledge_base\knowledge_base\*.py).Count
   (Get-ChildItem F:\github\finlab-stock-analyzer\kb-web\backend\knowledge_base\*.py).Count
   ```
   Both must print the same number.
3. Add a top-of-file note so future maintainers know this is a vendored copy — prepend to `kb-web/backend/knowledge_base/__init__.py`:
   ```python
   # Vendored from F:\knowledge_base\knowledge_base (2026-07-28).
   # This is a snapshot, not a live link — re-copy manually if the source package changes.
   ```
4. Commit is deferred to Task 12 (one commit per working milestone, not per file copy).

---

## Task 1: Backend scaffold — settings, requirements, FastAPI app skeleton

**Files:**
- Create: `kb-web/backend/requirements.txt`
- Create: `kb-web/backend/app/__init__.py`
- Create: `kb-web/backend/app/config.py`
- Create: `kb-web/backend/app/main.py`
- Create: `kb-web/backend/tests/__init__.py`
- Create: `kb-web/backend/tests/conftest.py`

**Steps:**

1. Write `kb-web/backend/requirements.txt`:
   ```
   fastapi==0.115.0
   uvicorn[standard]==0.30.0
   pydantic==2.9.0
   pydantic-settings==2.5.0
   pymongo==4.7.3
   PyJWT==2.8.0
   requests==2.32.3
   trafilatura==1.12.2
   anthropic==0.34.2
   python-multipart==0.0.9
   pytest==8.3.2
   httpx==0.27.0
   ```
   (`sentence-transformers` is deliberately **not** included — the vendored `semantic_search.py` falls back to the hashing embedding when it's absent, same as any environment without it. Keeps the Docker image small.)

2. Write `kb-web/backend/app/config.py`:
   ```python
   from __future__ import annotations

   from functools import lru_cache

   from pydantic_settings import BaseSettings


   class Settings(BaseSettings):
       kb_mongo_uri: str = "mongodb://localhost:27017"
       kb_mongo_db: str = "knowledge_base"
       kb_web_password: str = ""
       kb_api_token: str = ""
       jwt_secret: str = "dev-secret-change-me"
       anthropic_api_key: str = ""
       cors_origins: str = "http://localhost:5173"

       class Config:
           env_file = ".env"

       @property
       def cors_origin_list(self) -> list[str]:
           return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


   @lru_cache
   def get_settings() -> Settings:
       return Settings()
   ```

3. Write `kb-web/backend/app/__init__.py` (empty file).

4. Write `kb-web/backend/app/main.py`:
   ```python
   from fastapi import FastAPI
   from fastapi.middleware.cors import CORSMiddleware
   from fastapi.staticfiles import StaticFiles
   from pathlib import Path

   from .config import get_settings
   from .api import auth, notebooks, imports, ask

   settings = get_settings()

   app = FastAPI(title="Knowledge Base Web")

   app.add_middleware(
       CORSMiddleware,
       allow_origins=settings.cors_origin_list,
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )

   app.include_router(auth.router)
   app.include_router(notebooks.router)
   app.include_router(imports.router)
   app.include_router(ask.router)

   frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
   if frontend_dist.is_dir():
       app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="spa")
   ```
   (`app/api/` doesn't exist yet — created in Tasks 2-4. This file will fail to import until then; that's expected and gets fixed by the end of Task 4.)

5. Write `kb-web/backend/tests/__init__.py` (empty file).

6. Write `kb-web/backend/tests/conftest.py`:
   ```python
   import os
   import sys
   from pathlib import Path

   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

   os.environ.setdefault("KB_MONGO_DB", "knowledge_base_test")
   os.environ.setdefault("KB_WEB_PASSWORD", "test-password")
   os.environ.setdefault("KB_API_TOKEN", "test-cli-token")
   os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

   import pytest
   from pymongo import MongoClient


   @pytest.fixture
   def db():
       client = MongoClient(os.environ.get("KB_MONGO_URI", "mongodb://localhost:27017"))
       database = client[os.environ["KB_MONGO_DB"]]
       yield database
       client.drop_database(os.environ["KB_MONGO_DB"])
       client.close()
   ```

7. Create a local venv and install (run from `kb-web/backend/`):
   ```powershell
   cd F:\github\finlab-stock-analyzer\kb-web\backend
   python -m venv .venv
   .\.venv\Scripts\pip.exe install -r requirements.txt
   ```
   Expect this to fail right now (no `app/api` package) — that's fine, it's just to warm the venv before Task 2.

---

## Task 2: Backend — auth (JWT session + static CLI token)

**Files:**
- Create: `kb-web/backend/app/api/__init__.py`
- Create: `kb-web/backend/app/api/auth.py`
- Create: `kb-web/backend/app/deps.py`
- Create: `kb-web/backend/tests/test_auth.py`

**Steps:**

1. Write `kb-web/backend/app/deps.py` (shared auth dependency used by every protected route):
   ```python
   from __future__ import annotations

   from typing import Optional

   import jwt
   from fastapi import Header, HTTPException
   from pymongo import MongoClient
   from pymongo.database import Database

   from .config import get_settings


   def get_db() -> Database:
       settings = get_settings()
       client = MongoClient(settings.kb_mongo_uri)
       return client[settings.kb_mongo_db]


   def require_auth(authorization: Optional[str] = Header(default=None)) -> str:
       """Returns the caller identity ('web-user' or 'cli') or raises 401."""
       settings = get_settings()
       if not authorization:
           raise HTTPException(status_code=401, detail="Missing Authorization header.")
       parts = authorization.split(" ", 1)
       token = parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else authorization.strip()

       if settings.kb_api_token and token == settings.kb_api_token:
           return "cli"

       try:
           jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
           return "web-user"
       except Exception as exc:
           raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc
   ```

2. Write `kb-web/backend/app/api/__init__.py` (empty file).

3. Write `kb-web/backend/app/api/auth.py`:
   ```python
   from datetime import datetime, timedelta, timezone

   import jwt
   from fastapi import APIRouter, HTTPException
   from pydantic import BaseModel

   from ..config import get_settings

   router = APIRouter(prefix="/api", tags=["auth"])


   class LoginPayload(BaseModel):
       password: str


   class LoginResponse(BaseModel):
       token: str


   @router.post("/login", response_model=LoginResponse)
   def login(payload: LoginPayload) -> LoginResponse:
       settings = get_settings()
       if not settings.kb_web_password or payload.password != settings.kb_web_password:
           raise HTTPException(status_code=401, detail="Incorrect password.")
       token = jwt.encode(
           {"sub": "web-user", "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
           settings.jwt_secret,
           algorithm="HS256",
       )
       return LoginResponse(token=token)
   ```

4. Write `kb-web/backend/tests/test_auth.py`:
   ```python
   import os

   from fastapi.testclient import TestClient

   from app.main import app

   client = TestClient(app)


   def test_login_wrong_password_returns_401():
       response = client.post("/api/login", json={"password": "wrong"})
       assert response.status_code == 401


   def test_login_correct_password_returns_token():
       response = client.post("/api/login", json={"password": os.environ["KB_WEB_PASSWORD"]})
       assert response.status_code == 200
       assert "token" in response.json()


   def test_protected_route_without_token_returns_401():
       response = client.get("/api/notebooks")
       assert response.status_code == 401


   def test_protected_route_with_cli_token_succeeds():
       response = client.get(
           "/api/notebooks",
           headers={"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"},
       )
       assert response.status_code == 200
   ```
   (This test file references `/api/notebooks`, which doesn't exist until Task 3 — expected to fail until then.)

5. Run to confirm the login tests (the two that don't touch `/api/notebooks`) pass once `app/api/notebooks.py` exists as an empty-router stub. To unblock Task 2 in isolation, add a temporary stub now — write `kb-web/backend/app/api/notebooks.py`:
   ```python
   from fastapi import APIRouter, Depends

   from ..deps import require_auth

   router = APIRouter(prefix="/api", tags=["notebooks"])


   @router.get("/notebooks")
   def list_notebooks(_: str = Depends(require_auth)):
       return []
   ```
   (Real implementation replaces the body in Task 3 — this stub only exists so Task 2's tests are green independently.)

6. Also add matching empty-router stubs so `main.py` imports cleanly — `kb-web/backend/app/api/imports.py`:
   ```python
   from fastapi import APIRouter

   router = APIRouter(prefix="/api", tags=["imports"])
   ```
   and `kb-web/backend/app/api/ask.py`:
   ```python
   from fastapi import APIRouter

   router = APIRouter(prefix="/api", tags=["ask"])
   ```

7. Run the test suite:
   ```powershell
   cd F:\github\finlab-stock-analyzer\kb-web\backend
   .\.venv\Scripts\pip.exe install -r requirements.txt
   .\.venv\Scripts\python.exe -m pytest tests/test_auth.py -v
   ```
   Expect 4 passed.

---

## Task 3: Backend — notebooks endpoint (real implementation)

**Files:**
- Modify: `kb-web/backend/app/api/notebooks.py`
- Create: `kb-web/backend/tests/test_notebooks.py`

**Steps:**

1. Write the failing test first — `kb-web/backend/tests/test_notebooks.py`:
   ```python
   import os
   from datetime import datetime, timezone

   from fastapi.testclient import TestClient

   from app.main import app

   client = TestClient(app)
   AUTH = {"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"}


   def test_notebooks_lists_doc_type_grouped_counts(db):
       db.spec_docs.insert_many(
           [
               {
                   "doc_id": "a1",
                   "doc_type": "patent",
                   "updated_at": "2026-07-27T10:00:00+00:00",
                   "quality": {"pass": True},
                   "ui_knowledge": {"needs_ui_review": False},
               },
               {
                   "doc_id": "a2",
                   "doc_type": "patent",
                   "updated_at": "2026-07-28T10:00:00+00:00",
                   "quality": {"pass": False},
                   "ui_knowledge": {"needs_ui_review": True},
               },
           ]
       )
       response = client.get("/api/notebooks", headers=AUTH)
       assert response.status_code == 200
       body = response.json()
       assert body == [
           {
               "domain": "patent",
               "doc_count": 2,
               "last_updated": "2026-07-28T10:00:00+00:00",
               "quality_failed": 1,
               "needs_review": 1,
           }
       ]
   ```

2. Run it to confirm it fails (stub always returns `[]`):
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_notebooks.py -v
   ```
   Expect `assert [] == [{...}]` failure.

3. Replace `kb-web/backend/app/api/notebooks.py` with the real implementation:
   ```python
   from fastapi import APIRouter, Depends
   from pymongo.database import Database

   from ..deps import get_db, require_auth

   router = APIRouter(prefix="/api", tags=["notebooks"])


   @router.get("/notebooks")
   def list_notebooks(db: Database = Depends(get_db), _: str = Depends(require_auth)):
       pipeline = [
           {
               "$group": {
                   "_id": "$doc_type",
                   "doc_count": {"$sum": 1},
                   "last_updated": {"$max": "$updated_at"},
                   "quality_failed": {
                       "$sum": {"$cond": [{"$eq": ["$quality.pass", False]}, 1, 0]}
                   },
                   "needs_review": {
                       "$sum": {
                           "$cond": [{"$eq": ["$ui_knowledge.needs_ui_review", True]}, 1, 0]
                       }
                   },
               }
           },
           {"$sort": {"_id": 1}},
       ]
       rows = list(db.spec_docs.aggregate(pipeline))
       return [
           {
               "domain": row["_id"] or "(未分類)",
               "doc_count": row["doc_count"],
               "last_updated": row["last_updated"],
               "quality_failed": row["quality_failed"],
               "needs_review": row["needs_review"],
           }
           for row in rows
       ]
   ```

4. Re-run and confirm it passes:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_notebooks.py tests/test_auth.py -v
   ```
   Expect 5 passed.

---

## Task 4: Backend — file import endpoint

**Files:**
- Modify: `kb-web/backend/app/api/imports.py`
- Create: `kb-web/backend/tests/test_imports.py`

**Steps:**

1. Write the failing test — `kb-web/backend/tests/test_imports.py`:
   ```python
   import io
   import os

   from fastapi.testclient import TestClient

   from app.main import app

   client = TestClient(app)
   AUTH = {"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"}


   def test_import_file_rejects_doc_and_ppt():
       for name in ("legacy.doc", "legacy.ppt"):
           response = client.post(
               "/api/import/file",
               headers=AUTH,
               files={"file": (name, io.BytesIO(b"junk"), "application/octet-stream")},
               data={"domain": "patent"},
           )
           assert response.status_code == 400
           assert "LibreOffice" in response.json()["detail"] or "CLI" in response.json()["detail"]


   def test_import_file_accepts_markdown_and_indexes_it(db):
       content = b"# Test Doc\n\nThis is a test document about widgets."
       response = client.post(
           "/api/import/file",
           headers=AUTH,
           files={"file": ("widgets.md", io.BytesIO(content), "text/markdown")},
           data={"domain": "test-domain"},
       )
       assert response.status_code == 200
       body = response.json()
       assert body["imported"] == 1
       assert db.spec_docs.count_documents({"doc_type": "test-domain"}) == 1
   ```

2. Run to confirm it fails (stub router has no `/import/file` route → 404):
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_imports.py -v
   ```

3. Replace `kb-web/backend/app/api/imports.py`:
   ```python
   import tempfile
   from pathlib import Path

   from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
   from pymongo.database import Database

   from ..deps import get_db, require_auth
   from knowledge_base.spec_ingest import ingest_spec_documents
   from knowledge_base.semantic_search import rebuild_semantic_index

   router = APIRouter(prefix="/api", tags=["imports"])

   ALLOWED_SUFFIXES = {".docx", ".pptx", ".pdf", ".md", ".txt"}
   LEGACY_SUFFIXES = {".doc", ".ppt"}


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

       with tempfile.TemporaryDirectory() as tmp:
           tmp_path = Path(tmp) / file.filename
           tmp_path.write_bytes(await file.read())
           result = ingest_spec_documents(
               db=db,
               root_path=Path(tmp),
               forced_doc_type=domain,
               content_only=True,
           )
       rebuild_semantic_index(db, collections=["spec_docs"], force=False)
       return result
   ```

4. Re-run:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_imports.py -v
   ```
   Expect 2 passed. (The `sentence-transformers`-less environment uses the hashing embedding fallback automatically — no special-casing needed.)

---

## Task 5: Backend — URL import

**Files:**
- Modify: `kb-web/backend/app/api/imports.py`
- Modify: `kb-web/backend/tests/test_imports.py`

**Steps:**

1. Add the failing test to `kb-web/backend/tests/test_imports.py`:
   ```python
   from unittest.mock import patch


   def test_import_url_extracts_and_ingests(db):
       fake_html = "<html><body><article><h1>Widget Guide</h1><p>Widgets are great tools for testing.</p></article></body></html>"
       with patch("app.api.imports.requests.get") as mock_get:
           mock_get.return_value.status_code = 200
           mock_get.return_value.text = fake_html
           response = client.post(
               "/api/import/url",
               headers=AUTH,
               json={"url": "https://example.com/widgets", "domain": "test-domain"},
           )
       assert response.status_code == 200
       body = response.json()
       assert body["imported"] == 1
       doc = db.spec_docs.find_one({"doc_type": "test-domain"})
       assert doc["source_url"] == "https://example.com/widgets"


   def test_import_url_empty_extraction_returns_warning():
       with patch("app.api.imports.requests.get") as mock_get:
           mock_get.return_value.status_code = 200
           mock_get.return_value.text = "<html><body><script>var x=1;</script></body></html>"
           response = client.post(
               "/api/import/url",
               headers=AUTH,
               json={"url": "https://example.com/empty", "domain": "test-domain"},
           )
       assert response.status_code == 422
   ```

2. Run to confirm failure (no `/import/url` route yet).

3. Append to `kb-web/backend/app/api/imports.py`:
   ```python
   import requests
   import trafilatura
   from pydantic import BaseModel


   class UrlImportPayload(BaseModel):
       url: str
       domain: str


   @router.post("/import/url")
   def import_url(
       payload: UrlImportPayload,
       db: Database = Depends(get_db),
       _: str = Depends(require_auth),
   ):
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
   ```

4. Re-run:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_imports.py -v
   ```
   Expect 4 passed.

---

## Task 6: Backend — Q&A endpoint (Claude API)

**Files:**
- Modify: `kb-web/backend/app/api/ask.py`
- Create: `kb-web/backend/tests/test_ask.py`

**Steps:**

1. Write the failing test — `kb-web/backend/tests/test_ask.py`:
   ```python
   import os
   from unittest.mock import MagicMock, patch

   from fastapi.testclient import TestClient

   from app.main import app

   client = TestClient(app)
   AUTH = {"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"}


   def test_ask_returns_answer_with_citations(db):
       db.spec_docs.insert_one(
           {
               "doc_id": "d1",
               "title": "Widget Guide",
               "summary": "How widgets work",
               "doc_type": "test-domain",
               "tags": ["widget", "test-domain"],
               "source_path": "widgets.md",
           }
       )

       fake_message = MagicMock()
       fake_message.content = [MagicMock(text="Widgets are small testable things.")]

       with patch("app.api.ask.Anthropic") as MockAnthropic:
           MockAnthropic.return_value.messages.create.return_value = fake_message
           response = client.post(
               "/api/ask",
               headers=AUTH,
               json={"question": "What is a widget?", "domain": "test-domain"},
           )

       assert response.status_code == 200
       body = response.json()
       assert body["answer"] == "Widgets are small testable things."
       assert body["citations"][0]["title"] == "Widget Guide"


   def test_ask_without_api_key_returns_503(monkeypatch, db):
       monkeypatch.setenv("ANTHROPIC_API_KEY", "")
       from app.config import get_settings

       get_settings.cache_clear()
       response = client.post(
           "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
       )
       assert response.status_code == 503
       get_settings.cache_clear()
   ```

2. Run to confirm failure (stub has no `/ask` route).

3. Replace `kb-web/backend/app/api/ask.py`:
   ```python
   from anthropic import Anthropic
   from fastapi import APIRouter, Depends, HTTPException
   from pydantic import BaseModel
   from pymongo.database import Database

   from ..config import get_settings
   from ..deps import get_db, require_auth
   from knowledge_base.query import search_knowledge

   router = APIRouter(prefix="/api", tags=["ask"])


   class AskPayload(BaseModel):
       question: str
       domain: str | None = None


   class Citation(BaseModel):
       title: str
       source: str | None = None


   class AskResponse(BaseModel):
       answer: str
       citations: list[Citation]


   @router.post("/ask", response_model=AskResponse)
   def ask(
       payload: AskPayload,
       db: Database = Depends(get_db),
       _: str = Depends(require_auth),
   ):
       settings = get_settings()
       if not settings.anthropic_api_key:
           raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY 未設定，問答功能暫時無法使用。")

       tags = [payload.domain] if payload.domain else None
       results = search_knowledge(db=db, query_text=payload.question, top_k=6, include_tags=tags, scope="spec")

       citations = []
       context_lines = []
       for item in results:
           doc = item["doc"]
           title = doc.get("title", doc.get("doc_id", "unknown"))
           source = doc.get("source_url") or doc.get("relative_path") or doc.get("source_path")
           citations.append({"title": title, "source": source})
           context_lines.append(f"- {title}: {str(doc.get('content', doc.get('summary', '')))[:1500]}")
       context = "\n".join(context_lines) or "(沒有找到相關知識庫內容)"

       client = Anthropic(api_key=settings.anthropic_api_key)
       message = client.messages.create(
           model="claude-sonnet-4-5",
           max_tokens=1024,
           system=(
               "你是一個根據知識庫內容回答問題的助理。只根據下面提供的知識庫片段回答，"
               "如果片段裡沒有答案，誠實說不知道，不要編造。"
           ),
           messages=[
               {
                   "role": "user",
                   "content": f"知識庫片段：\n{context}\n\n問題：{payload.question}",
               }
           ],
       )
       answer_text = "".join(block.text for block in message.content if hasattr(block, "text"))
       return AskResponse(answer=answer_text, citations=citations)
   ```

4. Re-run:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_ask.py -v
   ```
   Expect 2 passed.

5. Run the full backend suite to confirm nothing regressed:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/ -v
   ```
   Expect all tests (auth 4 + notebooks 1 + imports 4 + ask 2 = 11) passed.

---

## Task 7: Frontend scaffold

**Files:**
- Create: `kb-web/frontend/package.json`
- Create: `kb-web/frontend/vite.config.js`
- Create: `kb-web/frontend/index.html`
- Create: `kb-web/frontend/src/main.js`
- Create: `kb-web/frontend/src/App.vue`
- Create: `kb-web/frontend/src/router.js`
- Create: `kb-web/frontend/src/api.js`

**Steps:**

1. Write `kb-web/frontend/package.json`:
   ```json
   {
     "name": "kb-web-frontend",
     "version": "1.0.0",
     "private": true,
     "type": "module",
     "scripts": {
       "dev": "vite",
       "build": "vite build",
       "preview": "vite preview"
     },
     "dependencies": {
       "axios": "^1.7.0",
       "pinia": "^2.1.0",
       "vue": "^3.4.0",
       "vue-router": "^4.3.0"
     },
     "devDependencies": {
       "@vitejs/plugin-vue": "^5.0.0",
       "vite": "^5.4.0"
     }
   }
   ```

2. Write `kb-web/frontend/vite.config.js`:
   ```javascript
   import { defineConfig } from 'vite'
   import vue from '@vitejs/plugin-vue'

   export default defineConfig({
     plugins: [vue()],
     server: {
       port: 5174,
       proxy: {
         '/api': {
           target: 'http://localhost:8090',
           changeOrigin: true,
         },
       },
     },
     build: {
       outDir: 'dist',
       assetsDir: 'assets',
     },
   })
   ```

3. Write `kb-web/frontend/index.html`:
   ```html
   <!doctype html>
   <html lang="zh-Hant">
     <head>
       <meta charset="UTF-8" />
       <title>知識庫</title>
     </head>
     <body>
       <div id="app"></div>
       <script type="module" src="/src/main.js"></script>
     </body>
   </html>
   ```

4. Write `kb-web/frontend/src/api.js`:
   ```javascript
   import axios from 'axios'

   const client = axios.create({ baseURL: '/api' })

   client.interceptors.request.use((config) => {
     const token = localStorage.getItem('kb_token')
     if (token) {
       config.headers.Authorization = `Bearer ${token}`
     }
     return config
   })

   client.interceptors.response.use(
     (response) => response,
     (error) => {
       if (error.response?.status === 401) {
         localStorage.removeItem('kb_token')
         window.location.href = '/login'
       }
       return Promise.reject(error)
     }
   )

   export default client
   ```

5. Write `kb-web/frontend/src/router.js`:
   ```javascript
   import { createRouter, createWebHistory } from 'vue-router'
   import Login from './views/Login.vue'
   import Notebooks from './views/Notebooks.vue'
   import Import from './views/Import.vue'
   import Ask from './views/Ask.vue'

   const router = createRouter({
     history: createWebHistory(),
     routes: [
       { path: '/login', component: Login },
       { path: '/', component: Notebooks },
       { path: '/import', component: Import },
       { path: '/ask', component: Ask },
     ],
   })

   router.beforeEach((to) => {
     const hasToken = !!localStorage.getItem('kb_token')
     if (to.path !== '/login' && !hasToken) {
       return '/login'
     }
   })

   export default router
   ```

6. Write `kb-web/frontend/src/main.js`:
   ```javascript
   import { createApp } from 'vue'
   import { createPinia } from 'pinia'
   import App from './App.vue'
   import router from './router.js'

   createApp(App).use(createPinia()).use(router).mount('#app')
   ```

7. Write `kb-web/frontend/src/App.vue`:
   ```vue
   <script setup>
   import { useRoute } from 'vue-router'
   const route = useRoute()
   </script>

   <template>
     <nav v-if="route.path !== '/login'">
       <router-link to="/">Notebook 總覽</router-link> |
       <router-link to="/import">資料匯入</router-link> |
       <router-link to="/ask">問答</router-link>
     </nav>
     <router-view />
   </template>
   ```

8. Create placeholder view files so the router resolves (real content in Tasks 8-10):
   - `kb-web/frontend/src/views/Login.vue`, `Notebooks.vue`, `Import.vue`, `Ask.vue` — each a minimal `<template><div>TODO</div></template>` for now.

9. Install and confirm dev server boots:
   ```powershell
   cd F:\github\finlab-stock-analyzer\kb-web\frontend
   npm install
   npm run dev
   ```
   Expect Vite to print `Local: http://localhost:5174/` with no errors. Stop it (Ctrl+C) once confirmed.

---

## Task 8: Frontend — Login view

**Files:**
- Modify: `kb-web/frontend/src/views/Login.vue`

**Steps:**

1. Write `kb-web/frontend/src/views/Login.vue`:
   ```vue
   <script setup>
   import { ref } from 'vue'
   import { useRouter } from 'vue-router'
   import api from '../api.js'

   const password = ref('')
   const error = ref('')
   const router = useRouter()

   async function submit() {
     error.value = ''
     try {
       const { data } = await api.post('/login', { password: password.value })
       localStorage.setItem('kb_token', data.token)
       router.push('/')
     } catch (e) {
       error.value = '密碼錯誤'
     }
   }
   </script>

   <template>
     <form @submit.prevent="submit">
       <h1>知識庫登入</h1>
       <input v-model="password" type="password" placeholder="密碼" autofocus />
       <button type="submit">登入</button>
       <p v-if="error" style="color: red">{{ error }}</p>
     </form>
   </template>
   ```

2. Verify manually in the browser after Task 11's docker-compose-free local run (covered there) — no isolated automated test for this view; it's exercised end-to-end in Task 11.

---

## Task 9: Frontend — Notebooks + Import views

**Files:**
- Modify: `kb-web/frontend/src/views/Notebooks.vue`
- Modify: `kb-web/frontend/src/views/Import.vue`

**Steps:**

1. Write `kb-web/frontend/src/views/Notebooks.vue`:
   ```vue
   <script setup>
   import { ref, onMounted } from 'vue'
   import api from '../api.js'

   const notebooks = ref([])
   const loading = ref(true)

   onMounted(async () => {
     const { data } = await api.get('/notebooks')
     notebooks.value = data
     loading.value = false
   })
   </script>

   <template>
     <h1>Notebook 總覽</h1>
     <p v-if="loading">載入中…</p>
     <table v-else>
       <thead>
         <tr><th>領域</th><th>篇數</th><th>最後更新</th><th>品質待複查</th><th>UI待複查</th></tr>
       </thead>
       <tbody>
         <tr v-for="nb in notebooks" :key="nb.domain">
           <td>{{ nb.domain }}</td>
           <td>{{ nb.doc_count }}</td>
           <td>{{ nb.last_updated }}</td>
           <td>{{ nb.quality_failed }}</td>
           <td>{{ nb.needs_review }}</td>
         </tr>
       </tbody>
     </table>
     <p v-if="!loading && notebooks.length === 0">目前沒有任何資料，先到「資料匯入」頁面加入內容。</p>
   </template>
   ```

2. Write `kb-web/frontend/src/views/Import.vue`:
   ```vue
   <script setup>
   import { ref } from 'vue'
   import api from '../api.js'

   const domain = ref('')
   const file = ref(null)
   const url = ref('')
   const result = ref(null)
   const error = ref('')

   function onFileChange(e) {
     file.value = e.target.files[0]
   }

   async function submitFile() {
     error.value = ''
     result.value = null
     const form = new FormData()
     form.append('file', file.value)
     form.append('domain', domain.value)
     try {
       const { data } = await api.post('/import/file', form)
       result.value = data
     } catch (e) {
       error.value = e.response?.data?.detail || '匯入失敗'
     }
   }

   async function submitUrl() {
     error.value = ''
     result.value = null
     try {
       const { data } = await api.post('/import/url', { url: url.value, domain: domain.value })
       result.value = data
     } catch (e) {
       error.value = e.response?.data?.detail || '匯入失敗'
     }
   }
   </script>

   <template>
     <h1>資料匯入</h1>
     <label>領域名稱 <input v-model="domain" placeholder="例如 patent" /></label>

     <fieldset>
       <legend>上傳檔案（.docx / .pptx / .pdf / .md / .txt）</legend>
       <input type="file" @change="onFileChange" />
       <button @click="submitFile" :disabled="!file || !domain">上傳並匯入</button>
     </fieldset>

     <fieldset>
       <legend>網址匯入</legend>
       <input v-model="url" placeholder="https://..." style="width: 400px" />
       <button @click="submitUrl" :disabled="!url || !domain">抓取並匯入</button>
     </fieldset>

     <p v-if="error" style="color: red">{{ error }}</p>
     <pre v-if="result">{{ JSON.stringify(result, null, 2) }}</pre>
   </template>
   ```

---

## Task 10: Frontend — Ask view

**Files:**
- Modify: `kb-web/frontend/src/views/Ask.vue`

**Steps:**

1. Write `kb-web/frontend/src/views/Ask.vue`:
   ```vue
   <script setup>
   import { ref } from 'vue'
   import api from '../api.js'

   const domain = ref('')
   const question = ref('')
   const answer = ref('')
   const citations = ref([])
   const loading = ref(false)
   const error = ref('')

   async function ask() {
     error.value = ''
     answer.value = ''
     citations.value = []
     loading.value = true
     try {
       const { data } = await api.post('/ask', { question: question.value, domain: domain.value || undefined })
       answer.value = data.answer
       citations.value = data.citations
     } catch (e) {
       error.value = e.response?.data?.detail || '問答失敗'
     } finally {
       loading.value = false
     }
   }
   </script>

   <template>
     <h1>問答</h1>
     <label>限定領域（留空 = 全部） <input v-model="domain" placeholder="例如 patent" /></label>
     <textarea v-model="question" placeholder="輸入問題" rows="3" style="width: 100%"></textarea>
     <button @click="ask" :disabled="!question || loading">{{ loading ? '思考中…' : '提問' }}</button>

     <p v-if="error" style="color: red">{{ error }}</p>
     <div v-if="answer">
       <h2>答案</h2>
       <p>{{ answer }}</p>
       <h3>引用來源</h3>
       <ul>
         <li v-for="(c, i) in citations" :key="i">{{ c.title }} — {{ c.source }}</li>
       </ul>
     </div>
   </template>
   ```

---

## Task 11: End-to-end local verification

**Steps:**

1. Start the backend locally against the **local** MongoDB (not the Zeabur one yet — migration happens in Task 12):
   ```powershell
   cd F:\github\finlab-stock-analyzer\kb-web\backend
   $env:KB_MONGO_URI="mongodb://localhost:27017"
   $env:KB_MONGO_DB="knowledge_base"
   $env:KB_WEB_PASSWORD="local-test-pw"
   $env:KB_API_TOKEN="local-test-token"
   $env:JWT_SECRET="local-test-jwt"
   $env:ANTHROPIC_API_KEY="<real key if testing /ask, else leave blank>"
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8090 --reload
   ```

2. In a second terminal, start the frontend dev server:
   ```powershell
   cd F:\github\finlab-stock-analyzer\kb-web\frontend
   npm run dev
   ```

3. Use the Browser preview tool to open `http://localhost:5174`, log in with `local-test-pw`, confirm the Notebooks page shows the existing local `patent` (49) and `finlab` test docs (6 — check actual `doc_type` value used during that earlier ingest, may show as blank/`(未分類)` since it wasn't tagged with `--doc-type`).

4. On the Import page, upload a small `.md` test file into a new domain (e.g. `smoke-test`) and confirm it appears in Notebooks afterward.

5. On the Ask page, ask a question scoped to `patent` (e.g. "上位語是什麼") and confirm an answer with citations comes back (requires a real `ANTHROPIC_API_KEY` for this step — if not available yet, confirm instead that the `/api/ask` call returns the 503 "not configured" error cleanly, not a crash).

6. Check the browser console (`read_console_messages`) for errors — must be empty of uncaught exceptions.

7. Stop both servers.

---

## Task 12: Data migration — local MongoDB → Zeabur MongoDB

**Steps:**

1. Dump the local `knowledge_base` database:
   ```powershell
   mongodump --uri="mongodb://localhost:27017" --db=knowledge_base --out="F:\knowledge_base\_migration_dump"
   ```

2. Restore into the Zeabur MongoDB under the same database name:
   ```powershell
   mongorestore --uri="mongodb://mongo:1ct9GNhC26SQTKIW5XpnLD4R3xi70eq8@172.234.90.16:30302" --db=knowledge_base "F:\knowledge_base\_migration_dump\knowledge_base"
   ```

3. Verify counts match on both sides:
   ```powershell
   mongosh "mongodb://localhost:27017/knowledge_base" --quiet --eval "db.spec_docs.countDocuments()"
   mongosh "mongodb://mongo:1ct9GNhC26SQTKIW5XpnLD4R3xi70eq8@172.234.90.16:30302/knowledge_base" --quiet --eval "db.spec_docs.countDocuments()"
   ```
   Both must print the same number (55, or more if Task 11's smoke-test doc was added — subtract 1 if so, or re-run the dump after deleting the smoke-test doc first).

4. Delete the local dump directory (contains a full data copy, no need to keep it after a verified restore):
   ```powershell
   Remove-Item -Recurse -Force "F:\knowledge_base\_migration_dump"
   ```

---

## Task 13: Dockerfile + Zeabur deployment config

**Files:**
- Create: `kb-web/Dockerfile`
- Create: `kb-web/.dockerignore`

**Steps:**

1. Write `kb-web/Dockerfile` (mirrors the repo-root `Dockerfile` pattern):
   ```dockerfile
   # Build frontend
   FROM node:20-alpine AS frontend-build
   WORKDIR /app/frontend
   COPY kb-web/frontend/package.json kb-web/frontend/package-lock.json* ./
   RUN npm install
   COPY kb-web/frontend/ ./
   RUN npm run build

   # Python backend
   FROM python:3.11-slim
   WORKDIR /app

   COPY kb-web/backend/requirements.txt ./
   RUN pip install --no-cache-dir -r requirements.txt

   COPY kb-web/backend/ ./backend/
   COPY --from=frontend-build /app/frontend/dist ./backend/frontend_dist

   ENV PYTHONPATH=/app/backend
   ENV PORT=8080
   EXPOSE 8080

   WORKDIR /app/backend
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
   ```

2. Write `kb-web/.dockerignore`:
   ```
   **/node_modules
   **/.venv
   **/__pycache__
   **/dist
   **/*.pyc
   ```

3. This step requires the Zeabur dashboard (browser) — not automatable from a plan step alone. In the same Zeabur project as `finlab-stock-analyzer`, create a new service, set its build root directory to `kb-web/` (so it picks up `kb-web/Dockerfile`, matching the repo-root-Dockerfile pattern one level down), and set environment variables: `KB_MONGO_URI`, `KB_MONGO_DB=knowledge_base`, `KB_WEB_PASSWORD`, `KB_API_TOKEN`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `CORS_ORIGINS`. Note the new service's `service-id` for the deploy command in Task 14.

---

## Task 14: Deploy and verify live

**Steps:**

1. From the repo root (per the existing house convention in `docs/00-開發流程.md` §八 — always deploy from repo root so Zeabur resolves the right build context):
   ```powershell
   cd F:\github\finlab-stock-analyzer
   $env:ZEABUR_TOKEN="<token>"
   npx zeabur deploy --project-id <PID> --service-id <NEW_SID> -i=false
   ```

2. Poll build status:
   ```powershell
   npx zeabur deployment list --service-id <NEW_SID> -i=false --json
   ```
   Confirm `planType` is docker (not static) and the build takes more than ~1 minute (a ~1-minute build indicates it was misdetected as static, per the documented pitfall).

3. Verify live:
   ```powershell
   curl -D - https://<new-domain>/
   curl -D - https://<new-domain>/api/notebooks -H "Authorization: Bearer $KB_API_TOKEN"
   ```
   First must return `200`; second must return `Content-Type: application/json` with the 55 migrated docs grouped by domain.

4. Open the live URL with the Browser preview tool, log in, click through Notebooks → Import → Ask, confirm no console errors.

---

## Task 15: Documentation + CLI usage note

**Files:**
- Create: `kb-web/README.md`
- Modify: `CLAUDE.md`

**Steps:**

1. Write `kb-web/README.md` with local dev instructions (venv setup, `npm run dev`, env vars) and the `curl` example from §2.1.1 of the spec for CLI/AI-tool callers.

2. Append to `CLAUDE.md`:
   ```markdown
   ## Knowledge Base Web

   A separate knowledge base (patent analysis methodology, and other domains as they're added) is queryable via the `kb-web` service. See `kb-web/README.md` for the `curl` invocation. Use it when a task touches patent-analysis terminology or methodology.
   ```

---

## Self-Review

- **Spec coverage**: login/JWT (Task 2) ✓, notebooks overview (Task 3) ✓, file import with `.doc`/`.ppt` rejection (Task 4) ✓, URL import with empty-extraction handling (Task 5) ✓, conversational Q&A with citations (Task 6) ✓, Vue frontend matching house stack (Tasks 7-10) ✓, incremental semantic indexing via `force=False` (Tasks 4-5, confirmed via `rebuild_semantic_index`'s existing hash-skip behavior — no new code needed) ✓, dual auth for CLI/web (Task 2) ✓, data migration (Task 12) ✓, separate Zeabur service deploy (Tasks 13-14) ✓, CLAUDE.md/README CLI docs (Task 15) ✓.
- **Placeholder scan**: no TBD/TODO left in final code blocks; the one intentional stub-then-replace pattern (Task 2 step 5 → Task 3 step 3) is explicit and self-contained, not an unfinished placeholder.
- **Type consistency**: `require_auth` returns a `str` identity used consistently as `_: str = Depends(require_auth)` across all four routers; `get_db`/`require_auth` imported from the same `app.deps` module everywhere; `ingest_spec_documents`/`rebuild_semantic_index`/`search_knowledge` signatures match the vendored source read directly from `F:\knowledge_base\knowledge_base`.
