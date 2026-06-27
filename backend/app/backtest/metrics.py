"""Performance metrics calculation for backtests."""

import numpy as np
from typing import Optional


def compute_metrics(
    equity_curve: list[dict],
    trades: list[dict],
    initial_capital: float,
) -> dict:
    """Compute backtest performance metrics."""
    if not equity_curve or not trades:
        return _empty_metrics()

    # Total return
    final_value = equity_curve[-1]["portfolio_value"]
    total_return = (final_value - initial_capital) / initial_capital

    # Annualized return
    days = len(equity_curve)
    years = days / 252
    annual_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1 if years > 0 else 0

    # Max drawdown
    values = [e["portfolio_value"] for e in equity_curve]
    max_drawdown = _max_drawdown(values)

    # Sharpe ratio (assume risk-free rate = 2%)
    daily_returns = np.diff(values) / np.array(values[:-1])
    sharpe = _sharpe_ratio(daily_returns, risk_free_annual=0.02)

    # Win rate
    winning = [t for t in trades if t["return"] > 0]
    win_rate = len(winning) / len(trades) if trades else 0

    # Profit factor
    gross_profit = sum(t["return"] for t in trades if t["return"] > 0)
    gross_loss = abs(sum(t["return"] for t in trades if t["return"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.99

    # Average holding days
    avg_holding = np.mean([t["holding_days"] for t in trades]) if trades else 0

    return {
        "total_return": round(total_return, 4),
        "annual_return": round(annual_return, 4),
        "max_drawdown": round(max_drawdown, 4),
        "sharpe_ratio": round(sharpe, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 2),
        "total_trades": len(trades),
        "avg_holding_days": round(float(avg_holding), 1),
    }


def _max_drawdown(values: list[float]) -> float:
    """Calculate maximum drawdown."""
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _sharpe_ratio(
    daily_returns: np.ndarray, risk_free_annual: float = 0.02
) -> float:
    """Calculate annualized Sharpe ratio."""
    if len(daily_returns) == 0:
        return 0.0
    rf_daily = (1 + risk_free_annual) ** (1 / 252) - 1
    excess = daily_returns - rf_daily
    std = np.std(excess)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(252))


def _empty_metrics() -> dict:
    return {
        "total_return": 0,
        "annual_return": 0,
        "max_drawdown": 0,
        "sharpe_ratio": 0,
        "win_rate": 0,
        "profit_factor": 0,
        "total_trades": 0,
        "avg_holding_days": 0,
    }
