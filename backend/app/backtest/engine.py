"""Backtest engine - executes strategies and generates results."""

import pandas as pd
import numpy as np
from typing import Optional
from .strategy import Strategy
from .metrics import compute_metrics
from ..analysis.technical import TechnicalAnalyzer


class BacktestEngine:
    """Core backtest execution engine."""

    def __init__(self):
        self.analyzer = TechnicalAnalyzer()

    def run(
        self,
        df: pd.DataFrame,
        strategy: Strategy,
        capital: float = 1_000_000,
        commission: float = 0.001425,
        tax: float = 0.003,
        slippage: float = 0.001,
    ) -> dict:
        """
        Execute backtest on price data with given strategy.

        Args:
            df: OHLCV DataFrame
            strategy: Strategy instance
            capital: Initial capital (TWD)
            commission: Commission rate per side (default 0.1425%)
            tax: Transaction tax on sell (default 0.3%)
            slippage: Fill slippage per side (default 0.1%): buy fills at
                close*(1+slippage), sell at close*(1-slippage)

        Returns:
            Dict with performance metrics (NET of all costs), equity curve,
            trades, monthly returns, and a cost breakdown.
        """
        if df.empty or len(df) < 2:
            return self._empty_result()

        # Compute indicators needed by strategy
        indicators = ["ma", "ema", "bollinger", "macd", "kd", "rsi", "adx", "atr", "volume"]
        df_with_indicators = self.analyzer.compute(df.copy(), indicators, strategy.params)

        # Generate signals
        signals = strategy.generate_signals(df_with_indicators)

        # Simulate trades
        trades = self._simulate_trades(
            df_with_indicators, signals, capital, commission, tax, slippage
        )

        # Build equity curve (cash-flow based, so all costs are reflected)
        equity_curve = self._build_equity_curve(df_with_indicators, trades, capital)

        # Compute metrics
        metrics = compute_metrics(equity_curve, trades, capital)

        # Monthly returns
        monthly_returns = self._compute_monthly_returns(equity_curve)

        total_costs = round(sum(t.get("cost_paid", 0.0) for t in trades), 2)
        return {
            "performance": metrics,
            "equity_curve": equity_curve,
            "trades": trades,
            "monthly_returns": monthly_returns,
            "costs": {
                "total_costs": total_costs,
                "cost_pct_of_capital": round(total_costs / capital, 4) if capital else 0,
                "commission": commission,
                "tax": tax,
                "slippage": slippage,
            },
        }

    def _simulate_trades(
        self, df: pd.DataFrame, signals: pd.Series, capital: float,
        commission: float, tax: float, slippage: float
    ) -> list[dict]:
        """Simulate trades based on signals.

        Fills include slippage; each trade carries both the gross return
        (`return`, price-to-price, kept for reference) and the NET result
        (`net_return`/`net_pnl`, from actual cash flows including
        commission + tax + slippage). `cost_paid` is the total friction in
        TWD versus a hypothetical free trade at close prices.
        """
        trades = []
        position = None
        cash = capital

        def _close_position(price, date_val, note=None):
            nonlocal cash, position
            exit_fill = price * (1 - slippage)
            proceeds = position["shares"] * exit_fill * (1 - commission - tax)
            cash += proceeds
            gross_ret = (price - position["entry_price"]) / position["entry_price"]
            net_pnl = proceeds - position["cost"]
            net_ret = net_pnl / position["cost"] if position["cost"] else 0.0
            # friction = what a costless close-price round trip would have made, minus reality
            frictionless = position["shares"] * (price - position["entry_price"])
            cost_paid = frictionless - net_pnl
            exit_date = str(date_val.date()) if hasattr(date_val, "date") else str(date_val)
            try:
                holding_days = (pd.Timestamp(exit_date) - pd.Timestamp(position["entry_date"])).days
            except Exception:
                holding_days = 0
            trade = {
                "entry_date": position["entry_date"],
                "exit_date": exit_date,
                "entry_price": position["entry_price"],
                "exit_price": price,
                "return": round(gross_ret, 4),
                "net_return": round(net_ret, 4),
                "net_pnl": round(net_pnl, 2),
                "cost_paid": round(cost_paid, 2),
                "cost": round(position["cost"], 2),
                "proceeds": round(proceeds, 2),
                "holding_days": holding_days,
                "shares": position["shares"],
            }
            if note:
                trade["note"] = note
            trades.append(trade)
            position = None

        for i in range(len(df)):
            signal = signals.iloc[i] if i < len(signals) else 0
            row = df.iloc[i]
            date = row["date"]
            price = row["close"]

            if signal == 1 and position is None:
                # Buy (fill above close by slippage)
                entry_fill = price * (1 + slippage)
                shares = int(cash * 0.95 / (entry_fill * 1000)) * 1000  # Round to lots
                if shares <= 0:
                    continue
                cost = shares * entry_fill * (1 + commission)
                cash -= cost
                position = {
                    "entry_date": str(date.date()) if hasattr(date, "date") else str(date),
                    "entry_price": price,
                    "entry_fill": entry_fill,
                    "shares": shares,
                    "cost": cost,
                }

            elif signal == -1 and position is not None:
                _close_position(price, date)

        # Close open position at end
        if position is not None and len(df) > 0:
            last_row = df.iloc[-1]
            _close_position(last_row["close"], last_row["date"], note="forced_close")

        return trades

    def _build_equity_curve(
        self, df: pd.DataFrame, trades: list[dict], capital: float
    ) -> list[dict]:
        """Build daily equity curve from actual cash flows.

        Uses each trade's real cost (incl. commission+slippage) and proceeds
        (net of commission+tax+slippage), so headline metrics computed from
        this curve are net of all trading costs — the old version marked
        price-to-price P&L and silently ignored friction.
        """
        cash = capital
        curve = []
        trade_idx = 0
        in_position = False
        shares = 0

        for i in range(len(df)):
            row = df.iloc[i]
            date = str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])

            # Enter today: pay the full (cost-inclusive) outlay
            if trade_idx < len(trades) and trades[trade_idx]["entry_date"] == date and not in_position:
                in_position = True
                shares = trades[trade_idx]["shares"]
                cash -= trades[trade_idx]["cost"]

            # Exit today: receive the net proceeds
            if trade_idx < len(trades) and trades[trade_idx]["exit_date"] == date and in_position:
                cash += trades[trade_idx]["proceeds"]
                in_position = False
                trade_idx += 1

            # Mark-to-market open position at close
            mtm = cash + (shares * row["close"] if in_position else 0)

            curve.append({
                "date": date,
                "portfolio_value": round(mtm, 2),
            })

        return curve

    def _compute_monthly_returns(self, equity_curve: list[dict]) -> list[dict]:
        """Compute monthly returns from equity curve."""
        if not equity_curve:
            return []

        df = pd.DataFrame(equity_curve)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        monthly = df["portfolio_value"].resample("ME").last()
        returns = monthly.pct_change().dropna()

        return [
            {"month": str(idx.strftime("%Y-%m")), "return": round(val, 4)}
            for idx, val in returns.items()
        ]

    def _empty_result(self) -> dict:
        return {
            "performance": {},
            "equity_curve": [],
            "trades": [],
            "monthly_returns": [],
            "costs": {"total_costs": 0, "cost_pct_of_capital": 0},
        }
