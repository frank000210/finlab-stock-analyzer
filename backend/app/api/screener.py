"""自然語言選股 API — W8."""

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from ..analysis.nl_screener import run_screener
from ..llm import LLMUnavailable, check_llm_rate_limit, is_llm_configured

router = APIRouter(prefix="/api/v1/screener", tags=["screener"])


class ScreenerQuery(BaseModel):
    query: str
    expand: bool = False  # X10：候選池太窄找不到結果時，前端可要求擴大範圍重查


@router.post("/query", dependencies=[Depends(check_llm_rate_limit)])
async def query_screener(payload: ScreenerQuery = Body(...)):
    """自然語言選股：LLM 只解析成篩選條件，實際篩選用網站既有數據跑數字比較。

    候選池取自產業關鍵字比對＋成交金額排序前 30 檔，不是全市場嚴格掃描，
    回應中誠實附上候選池大小。
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="請輸入選股條件")
    if len(query) > 200:
        raise HTTPException(status_code=400, detail="條件描述過長，請精簡在 200 字以內")
    if not is_llm_configured():
        raise HTTPException(status_code=503, detail="AI 服務尚未設定")
    try:
        return {"success": True, "data": await run_screener(query, expand=payload.expand)}
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"選股查詢失敗：{exc}")
