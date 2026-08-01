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
        mock_get_settings.return_value.opencode_api_key = "fake-key"
        mock_get_settings.return_value.llm_base_url = "https://opencode.ai/zen/go/v1"
        mock_get_settings.return_value.llm_model = "minimax-m2.5"
        mock_get_settings.return_value.llm_fallback_model = "qwen3.7-plus"
        mock_get_settings.return_value.llm_timeout_seconds = 90.0
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
        mock_get_settings.return_value.opencode_api_key = "fake-key"
        mock_get_settings.return_value.llm_base_url = "https://opencode.ai/zen/go/v1"
        mock_get_settings.return_value.llm_model = "minimax-m2.5"
        mock_get_settings.return_value.llm_fallback_model = "qwen3.7-plus"
        mock_get_settings.return_value.llm_timeout_seconds = 90.0
        mock_post.side_effect = [_fake_response(content=""), _fake_response(content="fallback answer")]

        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "fallback answer"
    assert mock_post.call_count == 2


def test_ask_without_api_key_returns_503(db):
    with patch("app.api.ask.get_settings") as mock_get_settings:
        mock_get_settings.return_value.opencode_api_key = ""
        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )
    assert response.status_code == 503
