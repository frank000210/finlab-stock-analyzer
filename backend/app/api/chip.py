"""籌碼分析 (Chip Analysis) API — 主力 / 散戶 / 大戶進出."""

import asyncio

from fastapi import APIRouter, HTTPException, Query

from ..analysis.chip_distribution import analyze_chip_distribution
from ..analysis.chip_cost import compute_major_cost
from ..analysis.major_players import analyze_major_players

router = APIRouter(prefix="/api/v1/stocks", tags=["chip"])


@router.get("/{symbol}/chip-analysis")
async def get_chip_analysis(
    symbol: str,
    days: int = Query(default=90, ge=20, le=365, description="法人動向分析天數"),
):
    """綜合籌碼分析：主力法人動向 + 大戶/散戶持股結構 + 大戶進出記錄."""
    try:
        cache_key = f"chip_analysis:v2:{symbol}:{days}"
        try:
            from ..db.cache import get_cache, set_cache
            cached = await get_cache(cache_key)
            if cached:
                return {"success": True, "data": cached}
        except Exception:
            set_cache = None  # type: ignore

        distribution, major = await asyncio.gather(
            analyze_chip_distribution(symbol),
            analyze_major_players(symbol, days),
            return_exceptions=True,
        )

        if isinstance(distribution, Exception):
            distribution = {"error": str(distribution)}
        if isinstance(major, Exception):
            major = {"error": str(major)}

        result = {
            "symbol": symbol,
            "distribution": distribution if "error" not in distribution else None,
            "distribution_error": distribution.get("error") if isinstance(distribution, dict) and "error" in distribution else None,
            "major_players": major if isinstance(major, dict) and "error" not in major else None,
            "major_players_error": major.get("error") if isinstance(major, dict) and "error" in major else None,
        }

        # 主力成本線 / 籌碼集中度 (複用法人量價資料)
        result["major_cost"] = compute_major_cost(result["major_players"])

        # Only cache when at least one section succeeded
        if (result["distribution"] or result["major_players"]):
            try:
                from ..db.cache import set_cache
                await set_cache(cache_key, result, "major_players")
            except Exception:
                pass

        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
