"""籌碼分析 (Chip Analysis) API — 主力 / 散戶 / 大戶進出."""

import asyncio

from fastapi import APIRouter, HTTPException, Query

from ..analysis.chip_distribution import analyze_chip_distribution
from ..analysis.chip_cost import compute_major_cost
from ..analysis.chip_signals import compute_sync_buy, compute_margin_ratio
from ..analysis.day_trade import analyze_day_trade
from ..analysis.major_players import analyze_major_players

router = APIRouter(prefix="/api/v1/stocks", tags=["chip"])


@router.get("/{symbol}/chip-analysis")
async def get_chip_analysis(
    symbol: str,
    days: int = Query(default=90, ge=20, le=365, description="法人動向分析天數"),
):
    """綜合籌碼分析：主力法人動向 + 大戶/散戶持股結構 + 大戶進出記錄."""
    try:
        cache_key = f"chip_analysis:v4:{symbol}:{days}"
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
        # 外資+投信同步買訊號 / 融資維持率估算 (複用法人與融資資料)
        result["sync_buy"] = compute_sync_buy(result["major_players"])
        result["margin_ratio"] = compute_margin_ratio(result["major_players"])
        # 當沖 / 隔日沖短線投機籌碼 (DayTrading + 法人量價總量)
        try:
            dt = await analyze_day_trade(symbol, result["major_players"])
            result["day_trade"] = dt if (dt and "error" not in dt) else None
        except Exception:
            result["day_trade"] = None

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


@router.get("/{symbol}/major-cost")
async def get_major_cost(
    symbol: str,
    days: int = Query(default=90, ge=20, le=365),
):
    """輕量主力成本摘要：供決策面板逐檔顯示主力估計成本與乖離."""
    try:
        cache_key = f"major_cost:v1:{symbol}:{days}"
        try:
            from ..db.cache import get_cache
            cached = await get_cache(cache_key)
            if cached:
                return {"success": True, "data": cached}
        except Exception:
            pass

        major = await analyze_major_players(symbol, days)
        if not isinstance(major, dict) or "error" in major:
            return {"success": True, "data": None}

        cost = compute_major_cost(major)
        if not cost:
            return {"success": True, "data": None}

        summary = {
            "symbol": symbol,
            "cost": cost.get("cost"),
            "last_close": cost.get("last_close"),
            "deviation": cost.get("deviation"),
            "cost_verdict": cost.get("cost_verdict"),
            "cost_tone": cost.get("cost_tone"),
            "concentration": cost.get("concentration"),
            "conc_verdict": cost.get("conc_verdict"),
        }
        try:
            from ..db.cache import set_cache
            await set_cache(cache_key, summary, "major_players")
        except Exception:
            pass

        return {"success": True, "data": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

