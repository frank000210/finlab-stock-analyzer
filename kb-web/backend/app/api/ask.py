from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.database import Database

from ..config import get_settings
from ..deps import get_db, require_auth
from knowledge_base.query import search_knowledge

router = APIRouter(prefix="/api", tags=["ask"])


class AskPayload(BaseModel):
    question: str
    domain: str | None = None


class Citation(BaseModel):
    title: str
    source: str | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskPayload,
    db: Database = Depends(get_db),
    _: str = Depends(require_auth),
):
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY 未設定，問答功能暫時無法使用。")

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

    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=(
            "你是一個根據知識庫內容回答問題的助理。只根據下面提供的知識庫片段回答，"
            "如果片段裡沒有答案，誠實說不知道，不要編造。"
        ),
        messages=[
            {
                "role": "user",
                "content": f"知識庫片段：\n{context}\n\n問題：{payload.question}",
            }
        ],
    )
    answer_text = "".join(block.text for block in message.content if hasattr(block, "text"))
    return AskResponse(answer=answer_text, citations=citations)
