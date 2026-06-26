"""Backtest API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, timedelta
import uuid

from ..crawler import StockPriceCrawler
from ..backtest import BacktestEngine
from ..backtest.strategies import ALL_STRATEGIES

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

# In-memory store for backtest results (replace with DB in production)
_backtest_results: dict = {}


class BacktestRequest(BaseModel):
    symbol: str
    strategy_id: str
    params: dict = {}
    date_range: dict  # {"start": "2021-01-01", "end": "2026-06-26"}
    capital: float = 1_000_000
    benchmark: str = "TAIEX"


@router.get("/strategies")
async def list_strategies():
    """List available backtest strategies with parameter schemas."""
    strategies = []
    for sid, cls in ALL_STRATEGIES.items():
        instance = cls()
        strategies.append({
            "strategy_id": sid,
            "name": instance.name,
            "description": instance.description,
            "params_schema": cls.params_schema(),
        })
    return {"success": True, "data": {"strategies": strategies}}


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """Execute a backtest."""
    if req.strategy_id not in ALL_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: {req.strategy_id}. Available: {list(ALL_STRATEGIES.keys())}",
        )

    start = req.date_range.get("start", str(date.today() - timedelta(days=365 * 5)))
    end = req.date_range.get("end", str(date.today()))

    try:
        # Fetch price data
        crawler = StockPriceCrawler()
        df = await crawler.get_price(req.symbol, start, end)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {req.symbol}")

        # Create strategy instance
        strategy_cls = ALL_STRATEGIES[req.strategy_id]
        strategy = strategy_cls(params=req.params)

        # Run backtest
        engine = BacktestEngine()
        result = engine.run(df, strategy, capital=req.capital)

        # Store result
        backtest_id = f"bt_{uuid.uuid4().hex[:12]}"
        _backtest_results[backtest_id] = {
            "backtest_id": backtest_id,
            "symbol": req.symbol,
            "strategy_id": req.strategy_id,
            "status": "completed",
            **result,
        }

        return {
            "success": True,
            "data": {
                "backtest_id": backtest_id,
                "symbol": req.symbol,
                "strategy_id": req.strategy_id,
                "status": "completed",
                "performance": result["performance"],
                "equity_curve": result["equity_curve"],
                "monthly_returns": result["monthly_returns"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{backtest_id}/result")
async def get_backtest_result(backtest_id: str):
    """Get backtest result by ID."""
    if backtest_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")

    result = _backtest_results[backtest_id]
    return {
        "success": True,
        "data": {
            "backtest_id": backtest_id,
            "symbol": result["symbol"],
            "strategy_id": result["strategy_id"],
            "status": result["status"],
            "performance": result["performance"],
            "equity_curve": result["equity_curve"],
            "monthly_returns": result["monthly_returns"],
        },
    }


@router.get("/{backtest_id}/trades")
async def get_backtest_trades(backtest_id: str):
    """Get trade history for a backtest."""
    if backtest_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")

    trades = _backtest_results[backtest_id].get("trades", [])
    return {
        "success": True,
        "data": {"items": trades},
    }
