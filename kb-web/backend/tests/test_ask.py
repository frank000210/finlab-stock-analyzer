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

    with patch("app.api.ask.Anthropic") as MockAnthropic, patch(
        "app.api.ask.get_settings"
    ) as mock_get_settings:
        mock_get_settings.return_value.anthropic_api_key = "fake-key"
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


def test_ask_without_api_key_returns_503(db):
    with patch("app.api.ask.get_settings") as mock_get_settings:
        mock_get_settings.return_value.anthropic_api_key = ""
        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )
    assert response.status_code == 503
