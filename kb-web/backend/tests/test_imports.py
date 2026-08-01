import io
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.api.imports import MAX_UPLOAD_BYTES

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"}

# example.com's real public IP -- used to mock DNS resolution so URL-import
# tests don't depend on real network access, while still exercising the
# actual SSRF-guard code path (ipaddress checks against a resolved IP).
_PUBLIC_ADDRINFO = [(2, 1, 6, "", ("93.184.216.34", 0))]


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


def test_import_file_rejects_oversized_upload():
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/api/import/file",
        headers=AUTH,
        files={"file": ("big.md", io.BytesIO(oversized), "text/markdown")},
        data={"domain": "test-domain"},
    )
    assert response.status_code == 413


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
    with patch("app.api.imports.socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO), patch(
        "app.api.imports.requests.get"
    ) as mock_get:
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
    with patch("app.api.imports.socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO), patch(
        "app.api.imports.requests.get"
    ) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<html><body><script>var x=1;</script></body></html>"
        response = client.post(
            "/api/import/url",
            headers=AUTH,
            json={"url": "https://example.com/empty", "domain": "test-domain"},
        )
    assert response.status_code == 422


def test_import_url_rejects_loopback_address():
    response = client.post(
        "/api/import/url",
        headers=AUTH,
        json={"url": "http://127.0.0.1:8080/admin", "domain": "test-domain"},
    )
    assert response.status_code == 422
    assert "內網" in response.json()["detail"]


def test_import_url_rejects_private_range_and_metadata_endpoint():
    for url in ("http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/"):
        response = client.post(
            "/api/import/url",
            headers=AUTH,
            json={"url": url, "domain": "test-domain"},
        )
        assert response.status_code == 422


def test_import_url_rejects_non_http_scheme():
    response = client.post(
        "/api/import/url",
        headers=AUTH,
        json={"url": "file:///etc/passwd", "domain": "test-domain"},
    )
    assert response.status_code == 422
