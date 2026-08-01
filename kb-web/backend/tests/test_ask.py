import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['KB_API_TOKEN']}"}


def _fake_response(status_code=200, content="Widgets are small testable things."):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _mock_settings(mock_get_settings, **overrides):
    settings = mock_get_settings.return_value
    settings.opencode_api_key = "fake-key"
    settings.llm_base_url = "https://opencode.ai/zen/go/v1"
    settings.llm_model = "minimax-m2.5"
    settings.llm_fallback_model = "qwen3.7-plus"
    settings.llm_timeout_seconds = 90.0
    settings.llm_daily_call_limit = 100
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


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

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings)
        mock_post.return_value = _fake_response()

        response = client.post(
            "/api/ask",
            headers=AUTH,
            json={"question": "What is a widget?", "domain": "test-domain"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Widgets are small testable things."
    assert body["citations"][0]["title"] == "Widget Guide"


def test_ask_falls_back_to_secondary_model_on_empty_content(db):
    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings)
        mock_post.side_effect = [_fake_response(content=""), _fake_response(content="fallback answer")]

        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "fallback answer"
    assert mock_post.call_count == 2


def test_ask_falls_back_when_primary_model_connection_fails(db):
    # NN6 regression: a network-layer error (not an HTTP error status) from
    # the primary model must still trigger the fallback model, not bubble
    # up as an unhandled 500.
    import httpx

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings)
        mock_post.side_effect = [httpx.ConnectTimeout("boom"), _fake_response(content="fallback answer")]

        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "fallback answer"


def test_ask_without_api_key_returns_503(db):
    with patch("app.api.ask.get_settings") as mock_get_settings:
        mock_get_settings.return_value.opencode_api_key = ""
        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )
    assert response.status_code == 503


def test_ask_rejects_once_daily_quota_exceeded(db):
    from datetime import date

    # Seed today's counter already at the limit (real DB write, not a mock --
    # the route's Depends(get_db) resolves to a separate client instance
    # than this fixture's, so mocking methods on `db` wouldn't be visible
    # to it; both point at the same underlying test database, so a real
    # seeded row is the reliable way to exercise this path).
    key = f"kb_web_llm_calls:{date.today().isoformat()}"
    db.sync_state.insert_one({"key": key, "value": 1})

    with patch("app.api.ask.get_settings") as mock_get_settings:
        _mock_settings(mock_get_settings, llm_daily_call_limit=1)
        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )
    assert response.status_code == 429
