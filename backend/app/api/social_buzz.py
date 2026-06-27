"""Social Buzz (社群熱度) API endpoint."""

from fastapi import APIRouter, Query, HTTPException

from ..analysis.social_buzz import analyze_social_buzz
from ..ai_agent.signal_generator import STOCK_NAMES

router = APIRouter(prefix="/api/v1/stocks", tags=["social-buzz"])


@router.get("/{symbol}/social-buzz")
async def get_social_buzz(symbol: str):
    """Analyze social media and news buzz for a stock."""
    try:
        stock_name = STOCK_NAMES.get(symbol, "")
        result = await analyze_social_buzz(symbol, stock_name)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
