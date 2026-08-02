"""Tests for /api/ask — PP 系列優化後的版本。

既有測試加上 enable_query_rewrite=False, max_agent_rounds=1 以維持單輪行為，
避免 mock httpx 次數不符；新增 PP1~PP7 各項的專屬測試。
"""
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
    # 預設關閉 PP1/PP3 以保持「1 次 LLM call」的舊測試行為
    settings.enable_query_rewrite = False
    settings.max_agent_rounds = 1
    settings.enable_web_search = False
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


# ─── 既有測試（維持相容）─────────────────────────────────────────────────────

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
        # AA7: answer must include [1] so PP5 citation parsing picks up Widget Guide
        mock_post.return_value = _fake_response(content="Widgets are small testable things. See [1].")

        response = client.post(
            "/api/ask",
            headers=AUTH,
            json={"question": "What is a widget?", "domain": "test-domain"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Widgets are small testable things" in body["answer"]
    # PP7：回應現在包含 steps 和 question_id
    assert "steps" in body
    assert "question_id" in body
    assert len(body["question_id"]) > 0
    # PP5: [1] 在答案中 → citations 應含 Widget Guide
    assert any(c["title"] == "Widget Guide" for c in body["citations"])


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
    # NN6 regression
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

    key = f"kb_web_llm_calls:{date.today().isoformat()}"
    db.sync_state.insert_one({"key": key, "value": 1})

    with patch("app.api.ask.get_settings") as mock_get_settings:
        _mock_settings(mock_get_settings, llm_daily_call_limit=1)
        response = client.post(
            "/api/ask", headers=AUTH, json={"question": "anything", "domain": "test-domain"}
        )
    assert response.status_code == 429


# ─── PP1 查詢改寫 ─────────────────────────────────────────────────────────────

def test_pp1_query_rewrite_expands_queries_and_adds_rewrite_step(db):
    """PP1：LLM 第一次呼叫回傳改寫後的查詢陣列，第二次才是真正的答案。"""
    db.spec_docs.insert_one({
        "doc_id": "pp1doc", "title": "Patent Claim Types", "summary": "independent vs dependent",
        "doc_type": "patent", "tags": ["patent", "claim"],
    })
    rewrite_resp = _fake_response(content='["獨立項 附屬項", "independent claim dependent claim"]')
    answer_resp = _fake_response(content="Patents have two main claim types [1].")

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings, enable_query_rewrite=True)
        mock_post.side_effect = [rewrite_resp, answer_resp]

        resp = client.post("/api/ask", headers=AUTH, json={"question": "請解釋專利請求項類型", "domain": "patent"})

    assert resp.status_code == 200
    body = resp.json()
    assert mock_post.call_count == 2
    # 第一個 step 應是 rewrite
    step_types = [s["type"] for s in body["steps"]]
    assert "rewrite" in step_types


def test_pp1_query_rewrite_fallback_on_invalid_json(db):
    """PP1：LLM 回傳無法解析的 JSON → 靜默回退回原問題，不拋例外。"""
    rewrite_resp = _fake_response(content="我無法改寫這個問題。")
    answer_resp = _fake_response(content="Here is the answer.")

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings, enable_query_rewrite=True)
        mock_post.side_effect = [rewrite_resp, answer_resp]

        resp = client.post("/api/ask", headers=AUTH, json={"question": "anything"})

    assert resp.status_code == 200
    # rewrite step 不應出現（退回原問題視為沒有改寫）
    step_types = [s["type"] for s in resp.json()["steps"]]
    assert "rewrite" not in step_types


# ─── PP3/PP4 Agentic 迴圈 ─────────────────────────────────────────────────────

def test_pp3_agentic_loop_executes_kb_search_tool(db):
    """PP3：模型輸出 TOOL_CALL kb_search，後端執行並回送結果，下輪才給最終答案。"""
    tool_call_resp = _fake_response(content='TOOL_CALL: {"action": "kb_search", "query": "patent claim"}')
    final_resp = _fake_response(content="After searching, here is the answer [2].")

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings, max_agent_rounds=2)
        mock_post.side_effect = [tool_call_resp, final_resp]

        resp = client.post("/api/ask", headers=AUTH, json={"question": "What is a patent claim?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "After searching, here is the answer [2]."
    kb_steps = [s for s in body["steps"] if s["type"] == "kb"]
    assert len(kb_steps) >= 2  # 初始查詢 + 工具查詢


def test_pp3_invalid_tool_call_treated_as_final_answer(db):
    """PP3：TOOL_CALL 解析失敗（無效 JSON）→ 整段視為最終答案。"""
    bad_resp = _fake_response(content="TOOL_CALL: not valid json --- so this is the answer")

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings, max_agent_rounds=2)
        mock_post.return_value = bad_resp

        resp = client.post("/api/ask", headers=AUTH, json={"question": "anything"})

    assert resp.status_code == 200
    # invalid TOOL_CALL → treated as final answer immediately (1 call)
    assert mock_post.call_count == 1


# ─── PP5 精確引用 ─────────────────────────────────────────────────────────────

def test_pp5_citation_parsed_from_answer_brackets(db):
    """PP5：答案裡有 [1]，citations 應只包含第 1 筆段落。"""
    db.spec_docs.insert_one({
        "doc_id": "c1", "title": "Cited Doc", "summary": "A cited document",
        "doc_type": "test", "tags": ["test"],
    })
    db.spec_docs.insert_one({
        "doc_id": "c2", "title": "Uncited Doc", "summary": "Not referenced",
        "doc_type": "test", "tags": ["test"],
    })

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings)
        # Answer only cites [1], not [2]
        mock_post.return_value = _fake_response(content="Based on [1], the answer is X.")

        resp = client.post("/api/ask", headers=AUTH, json={"question": "test citation", "domain": "test"})

    assert resp.status_code == 200
    citations = resp.json()["citations"]
    assert any(c["title"] == "Cited Doc" for c in citations)
    assert not any(c["title"] == "Uncited Doc" for c in citations)


# ─── PP6 對話歷史 ─────────────────────────────────────────────────────────────

def test_pp6_history_included_in_messages(db):
    """PP6：history 帶入後，httpx payload 應包含 user/assistant 歷史輪次。"""
    captured_payload = {}

    async def _fake_post(url, headers=None, json=None, **kwargs):
        captured_payload.update(json or {})
        return _fake_response()

    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_fake_post
    ):
        _mock_settings(mock_get_settings)
        resp = client.post("/api/ask", headers=AUTH, json={
            "question": "What about the second type?",
            "history": [
                {"role": "user", "content": "What is the first type?"},
                {"role": "assistant", "content": "The first type is independent claim."},
            ],
        })

    assert resp.status_code == 200
    msgs = captured_payload.get("messages", [])
    roles = [m["role"] for m in msgs]
    assert "user" in roles
    assert "assistant" in roles
    # 歷史輪次應在 system 之後、本次問題之前
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["content"] == "What about the second type?"


# ─── PP7 回饋端點 ─────────────────────────────────────────────────────────────

def test_pp7_feedback_stores_rating(db):
    """PP7：先問一個問題取得 question_id，再用 👍 送回饋。"""
    with patch("app.api.ask.get_settings") as mock_get_settings, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        _mock_settings(mock_get_settings)
        mock_post.return_value = _fake_response(content="Some answer.")
        ask_resp = client.post("/api/ask", headers=AUTH, json={"question": "any question"})

    assert ask_resp.status_code == 200
    question_id = ask_resp.json()["question_id"]

    fb_resp = client.post(
        "/api/ask/feedback",
        headers=AUTH,
        params={"question_id": question_id},
        json={"rating": 1},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["rating"] == 1

    doc = db.qa_history.find_one({"question_id": question_id})
    assert doc is not None
    assert doc["rating"] == 1


def test_pp7_feedback_404_for_unknown_id(db):
    resp = client.post(
        "/api/ask/feedback",
        headers=AUTH,
        params={"question_id": "nonexistent"},
        json={"rating": -1},
    )
    assert resp.status_code == 404
