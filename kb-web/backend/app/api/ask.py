"""PP 系列：問答品質七項優化。

PP1  查詢改寫   — 先讓 LLM 把問句展開成 2-3 組檢索詞，提升召回率
PP2  RRF 融合   — 多組查詢結果用 Reciprocal Rank Fusion 排序，候選擴大到 20 再取 8
PP3  Agentic 迴圈 — 模型可輸出 TOOL_CALL 再次查知識庫，最多 N 輪
PP4  上網搜尋   — TOOL_CALL web_search / fetch_url（DuckDuckGo + SSRF 防護）
PP5  精確引用   — 段落編號 [1][2]…，只列出模型在答案裡真正引用的來源
PP6  對話歷史   — 前端帶入前 N 輪 Q&A，追問能引用上文
PP7  過程透明＋回饋 — 回應含 steps（每輪做了什麼）+ question_id 供 👍/👎
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from pymongo import ReturnDocument
from pymongo.database import Database

from ..config import get_settings
from ..deps import get_db, require_auth
from knowledge_base.query import rrf_merge, search_knowledge

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ask"])

_USER_AGENT = "kb-web/1.0 (+https://frank210-kb-web.zeabur.app)"
_MAX_QUESTION_LEN = 800
_MAX_HISTORY_TURNS = 3    # PP6：最多帶入前 3 輪問答歷史
_PASSAGE_MAX_CHARS = 800  # 每段知識庫片段截斷上限


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    """PP6：單輪對話歷史。"""
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def _trim(cls, v: str) -> str:
        return v[:2000]


class AskPayload(BaseModel):
    question: str
    domain: str | None = None
    history: list[HistoryItem] = []  # PP6

    @field_validator("question")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("問題不可為空")
        return v[:_MAX_QUESTION_LEN]


class SearchStep(BaseModel):
    """PP7：單次工具呼叫的摘要。"""
    type: Literal["rewrite", "kb", "web", "fetch"]
    query: str
    hits: int


class Citation(BaseModel):
    """PP5：精確引用——只列出答案中出現 [N] 的來源。"""
    index: int
    title: str
    source: str | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    steps: list[SearchStep]   # PP7
    question_id: str          # PP7：供回饋端點使用


class FeedbackPayload(BaseModel):
    rating: Literal[1, -1]


# ─── 每日 quota ───────────────────────────────────────────────────────────────

def _bump_daily_quota(db: Database) -> None:
    """原子 $inc 計數並在超限時拋 429（NN2 手法）。可在同一次請求內多次呼叫。"""
    settings = get_settings()
    key = f"kb_web_llm_calls:{date.today().isoformat()}"
    try:
        doc = db.sync_state.find_one_and_update(
            {"key": key},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        used = int(doc.get("value", 1)) if doc else 1
    except Exception:
        logger.warning("Daily quota counter unavailable; allowing call through.")
        return
    if used > settings.llm_daily_call_limit:
        raise HTTPException(
            status_code=429,
            detail=f"今日問答次數已達上限（{settings.llm_daily_call_limit} 次），請明日再試。",
        )


# ─── LLM 呼叫 ─────────────────────────────────────────────────────────────────

async def _complete_raw(model: str, messages: list[dict], max_tokens: int = 1024) -> str:
    """向 OpenCode Go 送出完整 messages 陣列，回傳 content 字串。"""
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": messages,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.opencode_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": _USER_AGENT,
                },
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.warning("LLM request to %s failed: %s", model, exc)
        raise HTTPException(status_code=502, detail="AI 服務暫時無法連線") from exc

    if resp.status_code != 200:
        logger.warning("LLM upstream %s (%s): %s", resp.status_code, model, resp.text[:300])
        raise HTTPException(status_code=502, detail=f"AI 服務暫時無法使用（上游 {resp.status_code}）")

    data = resp.json()
    choices = data.get("choices") or []
    content = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    if not content:
        fin = choices[0].get("finish_reason") if choices else None
        logger.warning("LLM %s returned empty content (finish_reason=%s)", model, fin)
        raise HTTPException(status_code=502, detail="AI 回應內容為空")
    return content


async def _complete(messages: list[dict], max_tokens: int = 1024) -> str:
    """PP3：帶備援模型的多輪 LLM 呼叫（NN6 手法）。"""
    settings = get_settings()
    try:
        return await _complete_raw(settings.llm_model, messages, max_tokens)
    except HTTPException as first_err:
        fb = settings.llm_fallback_model
        if not fb or fb == settings.llm_model:
            raise
        logger.warning("Primary model %s failed (%s), trying %s", settings.llm_model, first_err.detail, fb)
        return await _complete_raw(fb, messages, max_tokens)


# 保留供舊測試使用的單輪介面
async def _complete_once(model: str, system: str, user: str) -> str:
    return await _complete_raw(model, [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])


async def _complete_with_fallback(system: str, user: str) -> str:
    return await _complete([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])


# ─── PP1: 查詢改寫 ────────────────────────────────────────────────────────────

_REWRITE_SYSTEM = (
    "你是資訊檢索專家，負責把使用者問題改寫成 2-3 個搜尋查詢，提高知識庫召回率。\n"
    "要求：涵蓋原問題不同面向（中英文術語、同義詞、上位概念）。\n"
    "回傳格式：JSON 陣列，例如 [\"查詢1\", \"查詢2\"]，不要有其他文字。"
)


async def _query_rewrite(question: str) -> list[str]:
    """PP1：LLM 把問題展開成 2-3 組查詢詞；失敗時回傳原問題。"""
    settings = get_settings()
    try:
        async with asyncio.timeout(15.0):
            raw = await _complete_raw(
                settings.llm_model,
                [{"role": "system", "content": _REWRITE_SYSTEM},
                 {"role": "user", "content": question}],
                max_tokens=128,
            )
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if m:
            queries = json.loads(m.group())
            if isinstance(queries, list):
                clean = [str(q).strip() for q in queries if str(q).strip()]
                if clean:
                    return clean[:3]
    except Exception as exc:
        logger.debug("query_rewrite failed (%s), falling back to original question", exc)
    return [question]


# ─── PP2: 多查詢 RRF 檢索 ─────────────────────────────────────────────────────

def _multi_query_retrieve(
    db: Database,
    queries: list[str],
    domain: str | None,
    candidate_k: int = 20,
    final_k: int = 8,
) -> list[dict[str, Any]]:
    """PP2：為每個查詢跑 search_knowledge，RRF 合併後取前 final_k 筆。"""
    tags = [domain] if domain else None
    result_lists = [
        search_knowledge(db=db, query_text=q, top_k=candidate_k, include_tags=tags, scope="spec")
        for q in queries
    ]
    return rrf_merge(result_lists)[:final_k]


# ─── PP5: 編號段落與引用解析 ──────────────────────────────────────────────────

def _build_numbered_context(passages: list[dict[str, Any]]) -> str:
    """PP5：把段落編號，回傳 prompt 用的文字。"""
    if not passages:
        return "（知識庫中沒有找到相關內容）"
    lines = []
    for i, item in enumerate(passages, start=1):
        doc = item["doc"]
        title = doc.get("title") or doc.get("doc_id", "")
        content = str(doc.get("content") or doc.get("summary") or "")[:_PASSAGE_MAX_CHARS]
        doc_type = doc.get("doc_type") or item.get("type", "")
        lines.append(f"[{i}] **{title}** ({doc_type})\n{content}")
    return "\n\n".join(lines)


def _parse_citations(answer: str, passages: list[dict[str, Any]]) -> list[Citation]:
    """PP5：從答案文字解析 [N] 引用。若模型未引用任何段落則回傳全部（向下相容）。"""
    indices = sorted(set(int(m) for m in re.findall(r'\[(\d+)\]', answer)))
    result: list[Citation] = []
    for idx in indices:
        if 1 <= idx <= len(passages):
            doc = passages[idx - 1]["doc"]
            result.append(Citation(
                index=idx,
                title=doc.get("title") or doc.get("doc_id", "unknown"),
                source=doc.get("source_url") or doc.get("relative_path") or doc.get("source_path"),
            ))
    if not result and passages:
        for i, item in enumerate(passages, start=1):
            doc = item["doc"]
            result.append(Citation(
                index=i,
                title=doc.get("title") or doc.get("doc_id", "unknown"),
                source=doc.get("source_url") or doc.get("relative_path") or doc.get("source_path"),
            ))
    return result


# ─── PP3/PP4: Agentic 迴圈 ────────────────────────────────────────────────────

_SYSTEM_WITH_TOOLS = """\
你是根據知識庫和（必要時）網路資料回答問題的助理。

**知識庫片段（引用時請用 [數字]，例如 [1][2]）：**
{context}

**工具使用（若現有片段不足以回答）：**
- 查知識庫：  TOOL_CALL: {{"action": "kb_search", "query": "查詢詞"}}
- 搜尋網路：  TOOL_CALL: {{"action": "web_search", "query": "搜尋詞"}}
- 讀取網頁：  TOOL_CALL: {{"action": "fetch_url", "url": "完整網址"}}

呼叫工具時整行只有 TOOL_CALL 那一行，不要混有其他文字。
若已可作答，直接給出答案，請用 [N] 標記引用的片段編號。
"""

_SYSTEM_NO_TOOLS = """\
你是根據知識庫內容回答問題的助理。只根據下面片段回答，若沒有答案請如實說明。

**知識庫片段（引用時請用 [數字]）：**
{context}
"""

_TOOL_CALL_RE = re.compile(r'^\s*TOOL_CALL:\s*(\{.*\})\s*$', re.MULTILINE)


def _parse_tool_call(response: str) -> dict[str, str] | None:
    m = _TOOL_CALL_RE.search(response)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        if data.get("action") in ("kb_search", "web_search", "fetch_url"):
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


# ─── PP7: 問答歷史儲存 ────────────────────────────────────────────────────────

def _store_qa(db: Database, question_id: str, question: str, answer: str, steps: list[SearchStep]) -> None:
    try:
        db.qa_history.insert_one({
            "question_id": question_id,
            "question": question,
            "answer": answer,
            "steps": [s.model_dump() for s in steps],
            "rating": None,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logger.debug("_store_qa failed (non-critical)")


# ─── 主端點 ───────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskPayload,
    db: Database = Depends(get_db),
    _: str = Depends(require_auth),
):
    settings = get_settings()
    if not settings.opencode_api_key:
        raise HTTPException(status_code=503, detail="OPENCODE_API_KEY 未設定，問答功能暫時無法使用。")

    question_id = uuid.uuid4().hex[:16]
    steps: list[SearchStep] = []
    passage_pool: list[dict[str, Any]] = []

    # ── PP1: 查詢改寫 ─────────────────────────────────────────────────────────
    if settings.enable_query_rewrite:
        _bump_daily_quota(db)
        queries = await _query_rewrite(payload.question)
        if queries != [payload.question]:
            steps.append(SearchStep(type="rewrite", query=" | ".join(queries), hits=len(queries)))
    else:
        queries = [payload.question]

    # ── PP2: 多查詢 RRF 檢索 ──────────────────────────────────────────────────
    passage_pool = _multi_query_retrieve(db, queries, payload.domain)
    steps.append(SearchStep(type="kb", query=queries[0], hits=len(passage_pool)))
    next_passage_idx = len(passage_pool) + 1

    # ── PP3: 建構初始 prompt（PP5 編號段落）────────────────────────────────────
    context_text = _build_numbered_context(passage_pool)
    system_tpl = _SYSTEM_WITH_TOOLS if settings.enable_web_search else _SYSTEM_NO_TOOLS
    system_prompt = system_tpl.format(context=context_text)

    # PP6：帶入對話歷史（前 N 輪 × 2 messages）
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in payload.history[- _MAX_HISTORY_TURNS * 2:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": payload.question})

    # ── PP3/PP4: Agentic 迴圈 ─────────────────────────────────────────────────
    answer_text = ""
    for _round in range(settings.max_agent_rounds + 1):
        _bump_daily_quota(db)
        response = await _complete(messages)

        tool_call = _parse_tool_call(response)
        if tool_call is None:
            answer_text = response
            break

        messages.append({"role": "assistant", "content": response})
        action = tool_call.get("action", "")

        if action == "kb_search":
            query = str(tool_call.get("query", ""))
            new_passages = _multi_query_retrieve(db, [query], payload.domain, candidate_k=10, final_k=4)
            steps.append(SearchStep(type="kb", query=query, hits=len(new_passages)))
            if new_passages:
                extra = []
                for i, item in enumerate(new_passages, start=next_passage_idx):
                    doc = item["doc"]
                    title = doc.get("title") or doc.get("doc_id", "")
                    content = str(doc.get("content") or doc.get("summary") or "")[:_PASSAGE_MAX_CHARS]
                    extra.append(f"[{i}] **{title}**\n{content}")
                    passage_pool.append(item)
                next_passage_idx += len(new_passages)
                tool_result = "新增片段：\n\n" + "\n\n".join(extra)
            else:
                tool_result = "（此查詢在知識庫中沒有找到新內容）"

        elif action == "web_search":
            from .web_tools import web_search  # lazy import
            query = str(tool_call.get("query", ""))
            tool_result = await asyncio.to_thread(web_search, query)
            steps.append(SearchStep(type="web", query=query, hits=0 if tool_result.startswith("（") else 1))

        elif action == "fetch_url":
            from .web_tools import fetch_url  # lazy import
            url = str(tool_call.get("url", ""))
            tool_result = await asyncio.to_thread(fetch_url, url)
            steps.append(SearchStep(type="fetch", query=url, hits=0 if "（無法" in tool_result else 1))

        else:
            tool_result = "（不支援的工具動作）"

        messages.append({
            "role": "user",
            "content": f"工具結果：\n{tool_result}\n\n請繼續作答，或再次呼叫工具取得更多資料。",
        })
    else:
        for m in reversed(messages):
            if m["role"] == "assistant":
                answer_text = m["content"]
                break
        if not answer_text:
            answer_text = "（超過最大檢索輪數，無法提供完整答案）"

    # ── PP5: 精確引用 ─────────────────────────────────────────────────────────
    citations = _parse_citations(answer_text, passage_pool)

    # ── PP7: 儲存問答 ─────────────────────────────────────────────────────────
    _store_qa(db, question_id, payload.question, answer_text, steps)

    return AskResponse(
        answer=answer_text,
        citations=citations,
        steps=steps,
        question_id=question_id,
    )


@router.post("/ask/feedback")
async def ask_feedback(
    question_id: str,
    payload: FeedbackPayload,
    db: Database = Depends(get_db),
    _: str = Depends(require_auth),
):
    """PP7：👍/👎 回饋，更新對應問答紀錄的 rating 欄位。"""
    result = db.qa_history.update_one(
        {"question_id": question_id},
        {"$set": {"rating": payload.rating, "rated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="找不到該問答紀錄。")
    return {"ok": True, "question_id": question_id, "rating": payload.rating}
