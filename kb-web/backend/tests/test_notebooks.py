import os

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
