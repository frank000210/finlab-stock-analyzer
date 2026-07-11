"""Backtest API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, timedelta
import uuid

import pandas as pd

from ..crawler import StockPriceCrawler
from ..backtest import BacktestEngine
from ..backtest.strategies import ALL_STRATEGIES

# 過擬合防護（A3）門檻：樣本外交易數低於此值視為不可靠，不下判斷。
_MIN_OOS_TRADES = 5
_MIN_TOTAL_TRADES_FOR_STATS = 30


def _check_overfit(engine: BacktestEngine, df: pd.DataFrame, strategy, capital: float,
                    commission: float, slippage: float) -> dict:
    """樣本內／樣本外 70/30 走勢驗證：同一份已下載的資料切兩段重跑同一策略
    同一組參數，比較樣本外是否還撐得住。不額外呼叫資料源。"""
    dates = pd.to_datetime(df["date"]).sort_values().reset_index(drop=True)
    n = len(dates)
    split_idx = int(n * 0.7)
    if split_idx < _MIN_OOS_TRADES or (n - split_idx) < _MIN_OOS_TRADES:
        return {"available": False, "note": "資料筆數不足以拆分樣本內／外，略過過擬合檢查。"}

    split_date = dates.iloc[split_idx]
    df_dates = pd.to_datetime(df["date"])
    is_df = df[df_dates <= split_date].reset_index(drop=True)
    oos_df = df[df_dates > split_date].reset_index(drop=True)

    is_result = engine.run(is_df, strategy, capital=capital, commission=commission, slippage=slippage)
    oos_result = engine.run(oos_df, strategy, capital=capital, commission=commission, slippage=slippage)
    is_perf, oos_perf = is_result["performance"], oos_result["performance"]

    oos_trades = oos_perf.get("total_trades", 0)
    if oos_trades < _MIN_OOS_TRADES:
        return {
            "available": False,
            "note": f"樣本外只有 {oos_trades} 筆交易，太少無法判斷是否過擬合。",
            "split_date": str(split_date.date()),
        }

    is_annual = is_perf.get("annual_return", 0)
    oos_annual = oos_perf.get("annual_return", 0)

    if oos_annual <= 0 and is_annual > 0:
        verdict, label = "high", "⚠ 樣本外由賺轉賠，過擬合風險高——參數很可能是套在歷史資料上調出來的"
    elif is_annual > 0 and oos_annual < is_annual * 0.5:
        verdict, label = "medium", "樣本外報酬明顯衰退（不到樣本內一半），留意過擬合、建議降低參數複雜度"
    else:
        verdict, label = "low", "樣本外表現與樣本內相近，過擬合疑慮較低"

    return {
        "available": True,
        "split_date": str(split_date.date()),
        "in_sample": {
            "start": str(is_df["date"].iloc[0])[:10], "end": str(is_df["date"].iloc[-1])[:10],
            "annual_return": is_perf.get("annual_return", 0), "win_rate": is_perf.get("win_rate", 0),
            "profit_factor": is_perf.get("profit_factor", 0), "total_trades": is_perf.get("total_trades", 0),
        },
        "out_sample": {
            "start": str(oos_df["date"].iloc[0])[:10], "end": str(oos_df["date"].iloc[-1])[:10],
            "annual_return": oos_annual, "win_rate": oos_perf.get("win_rate", 0),
            "profit_factor": oos_perf.get("profit_factor", 0), "total_trades": oos_trades,
        },
        "verdict": verdict,
        "verdict_label": label,
    }

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
    # 真實交易成本（台股散戶預設）：手續費/邊 0.1425%、賣出證交稅 0.3%（引擎內固定）、滑價/邊 0.1%
    commission: float = 0.001425
    slippage: float = 0.001


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

        # Run backtest (net of commission/tax/slippage)
        commission = max(req.commission, 0.0)
        slippage = max(req.slippage, 0.0)
        engine = BacktestEngine()
        result = engine.run(df, strategy, capital=req.capital, commission=commission, slippage=slippage)

        # 過擬合防護（A3）：同一份資料切樣本內/外重跑同一策略同一組參數。
        overfit_check = _check_overfit(engine, df, strategy, req.capital, commission, slippage)
        total_trades = result["performance"].get("total_trades", 0)
        if total_trades < _MIN_TOTAL_TRADES_FOR_STATS:
            overfit_check = {
                **overfit_check,
                "low_trade_count": True,
                "low_trade_note": f"總交易數僅 {total_trades} 筆（建議 ≥ {_MIN_TOTAL_TRADES_FOR_STATS} 筆），統計效力有限，數字僅供參考。",
            }

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
                "costs": result.get("costs", {}),
                "overfit_check": overfit_check,
                "mfe_mae": result.get("mfe_mae", {}),
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
