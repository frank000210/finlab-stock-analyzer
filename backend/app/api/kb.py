"""知識庫問答代理端點。

前端無法直接持有 KB_API_TOKEN，透過本後端代理，token 只存在伺服器環境變數。
管理員才能呼叫（require_admin）；非管理員在前端看不到此頁面，後端仍雙重保護。
"""

import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .admin import require_admin

router = APIRouter(prefix="/api/v1/kb", tags=["kb"])

_KB_WEB_URL = os.environ.get("KB_WEB_URL", "https://frank210-kb-web.zeabur.app").rstrip("/")
_KB_TIMEOUT = 60.0


def _kb_headers() -> dict[str, str]:
    token = os.environ.get("KB_API_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="KB_API_TOKEN 尚未在伺服器設定。")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class KbAskPayload(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    domain: Optional[str] = Field(None, max_length=100)


@router.post("/ask", dependencies=[Depends(require_admin)])
async def kb_ask(payload: KbAskPayload):
    """向知識庫提問，回傳 AI 答案與引用來源。"""
    body: dict = {"question": payload.question}
    if payload.domain:
        body["domain"] = payload.domain

    try:
        async with httpx.AsyncClient(timeout=_KB_TIMEOUT) as client:
            resp = await client.post(
                f"{_KB_WEB_URL}/api/ask",
                headers=_kb_headers(),
                json=body,
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"KB 服務錯誤 {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="KB 服務逾時（60s），請稍後再試。")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"無法連接知識庫：{e}")

    return resp.json()


@router.get("/domains", dependencies=[Depends(require_admin)])
async def kb_domains():
    """列出知識庫所有領域與文件數量。"""
    try:
        async with httpx.AsyncClient(timeout=_KB_TIMEOUT) as client:
            resp = await client.get(
                f"{_KB_WEB_URL}/api/notebooks",
                headers=_kb_headers(),
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"KB 服務錯誤 {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"無法連接知識庫：{e}")

    return {"data": resp.json()}
