"""Major Players (主力動向) API endpoint."""

from fastapi import APIRouter, Query, HTTPException

from ..analysis.major_players import analyze_major_players

router = APIRouter(prefix="/api/v1/stocks", tags=["major-players"])


@router.get("/{symbol}/major-players")
async def get_major_players_analysis(
    symbol: str,
    days: int = Query(default=90, ge=20, le=365, description="分析天數"),
):
    """Analyze major player (主力) accumulation/distribution patterns."""
    try:
        result = await analyze_major_players(symbol, days)
        if "error" in result:
            return {"success": False, "error": result["error"], "data": None}
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
