from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)


def test_auth_mode_defaults_to_private():
    assert client.get("/api/auth-mode").json() == {"public": False}


def test_private_mode_still_requires_auth_for_reads(db):
    assert client.get("/api/notebooks").status_code == 401


def test_public_mode_opens_reads_but_not_imports(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "kb_web_public", True)
    assert client.get("/api/auth-mode").json() == {"public": True}
    assert client.get("/api/notebooks").status_code == 200
    # 匯入是寫入，公開模式下仍要 token，避免任何人往知識庫灌資料
    resp = client.post("/api/import/url", json={"url": "https://example.com", "domain": "x"})
    assert resp.status_code == 401
