import io
import os
from unittest.mock import patch

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


def test_import_url_extracts_and_ingests(db):
    fake_html = (
        "<html><body><article><h1>Widget Guide</h1>"
        "<p>Widgets are great tools for testing import pipelines end to end.</p>"
        "<p>This paragraph adds enough real content so trafilatura's extraction "
        "clears the minimum-length check used to detect empty/JS-only pages.</p>"
        "</article></body></html>"
    )
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
