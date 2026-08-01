import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.database import Database

from ..config import get_settings
from ..deps import get_db, require_auth
from knowledge_base.query import search_knowledge

router = APIRouter(prefix="/api", tags=["ask"])

# OpenCode Go sits behind Cloudflare; the default httpx/Python UA gets
# bot-blocked (403, error 1010). Must send a recognizable UA -- see
# backend/app/llm/client.py for the (proven in production) reference.
_USER_AGENT = "kb-web/1.0 (+https://frank210-kb-web.zeabur.app)"

_SYSTEM_PROMPT = (
    "你是一個根據知識庫內容回答問題的助理。只根據下面提供的知識庫片段回答，"
    "如果片段裡沒有答案，誠實說不知道，不要編造。"
)


class AskPayload(BaseModel):
    question: str
    domain: str | None = None


class Citation(BaseModel):
    title: str
    source: str | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]


async def _complete_once(model: str, system: str, user: str) -> str:
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
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
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"AI 服務暫時無法使用（上游狀態 {resp.status_code}）")

    data = resp.json()
    choices = data.get("choices") or []
    content = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    if not content:
        raise HTTPException(status_code=502, detail="AI 回應內容為空")
    return content


async def _complete_with_fallback(system: str, user: str) -> str:
    settings = get_settings()
    try:
        return await _complete_once(settings.llm_model, system, user)
    except HTTPException:
        if not settings.llm_fallback_model or settings.llm_fallback_model == settings.llm_model:
            raise
        return await _complete_once(settings.llm_fallback_model, system, user)


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskPayload,
    db: Database = Depends(get_db),
    _: str = Depends(require_auth),
):
    settings = get_settings()
    if not settings.opencode_api_key:
        raise HTTPException(status_code=503, detail="OPENCODE_API_KEY 未設定，問答功能暫時無法使用。")

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

    user_message = f"知識庫片段：\n{context}\n\n問題：{payload.question}"
    answer_text = await _complete_with_fallback(_SYSTEM_PROMPT, user_message)
    return AskResponse(answer=answer_text, citations=citations)
