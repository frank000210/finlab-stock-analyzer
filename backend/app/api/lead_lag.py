"""Lead-Lag analysis API endpoint."""

from fastapi import APIRouter, Query, HTTPException

from ..analysis.lead_lag import analyze_lead_lag, SECTOR_LEADERS

router = APIRouter(prefix="/api/v1/stocks", tags=["lead-lag"])


@router.get("/{symbol}/lead-lag")
async def get_lead_lag_analysis(
    symbol: str,
    benchmark: str = Query(default="TAIEX", description="基準：TAIEX 或個股代碼"),
    days: int = Query(default=365, ge=90, le=1825, description="分析天數"),
    max_lag: int = Query(default=20, ge=5, le=40, description="最大滯後天數"),
):
    """Analyze lead/lag relationship between stock and benchmark."""
    try:
        result = await analyze_lead_lag(symbol, benchmark, days, max_lag)
        if "error" in result:
            return {"success": False, "error": result["error"], "data": None}
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lead-lag/leaders")
async def get_sector_leaders():
    """Get available sector leader benchmarks."""
    leaders = [
        {"sector": k, "symbol": v["symbol"], "name": v["name"]}
        for k, v in SECTOR_LEADERS.items()
    ]
    return {"success": True, "data": leaders}
