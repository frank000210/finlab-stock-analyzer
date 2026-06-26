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
    ) -> dict:
        """
        Execute backtest on price data with given strategy.
        
        Args:
            df: OHLCV DataFrame
            strategy: Strategy instance
            capital: Initial capital (TWD)
            commission: Commission rate (default 0.1425%)
            tax: Transaction tax on sell (default 0.3%)
            
        Returns:
            Dict with performance metrics, equity curve, trades
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
            df_with_indicators, signals, capital, commission, tax
        )

        # Build equity curve
        equity_curve = self._build_equity_curve(df_with_indicators, trades, capital)

        # Compute metrics
        metrics = compute_metrics(equity_curve, trades, capital)

        # Monthly returns
        monthly_returns = self._compute_monthly_returns(equity_curve)

        return {
            "performance": metrics,
            "equity_curve": equity_curve,
            "trades": trades,
            "monthly_returns": monthly_returns,
        }

    def _simulate_trades(
        self, df: pd.DataFrame, signals: pd.Series, capital: float,
        commission: float, tax: float
    ) -> list[dict]:
        """Simulate trades based on signals."""
        trades = []
        position = None
        cash = capital

        for i in range(len(df)):
            signal = signals.iloc[i] if i < len(signals) else 0
            row = df.iloc[i]
            date = row["date"]
            price = row["close"]

            if signal == 1 and position is None:
                # Buy
                shares = int(cash * 0.95 / (price * 1000)) * 1000  # Round to lots
                if shares <= 0:
                    continue
                cost = shares * price * (1 + commission)
                cash -= cost
                position = {
                    "entry_date": str(date.date()) if hasattr(date, "date") else str(date),
                    "entry_price": price,
                    "shares": shares,
                    "cost": cost,
                }

            elif signal == -1 and position is not None:
                # Sell
                proceeds = position["shares"] * price * (1 - commission - tax)
                cash += proceeds
                ret = (price - position["entry_price"]) / position["entry_price"]
                entry_date = position["entry_date"]
                exit_date = str(date.date()) if hasattr(date, "date") else str(date)

                # Calculate holding days
                try:
                    holding_days = (pd.Timestamp(exit_date) - pd.Timestamp(entry_date)).days
                except Exception:
                    holding_days = 0

                trades.append({
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "return": round(ret, 4),
                    "holding_days": holding_days,
                    "shares": position["shares"],
                })
                position = None

        # Close open position at end
        if position is not None and len(df) > 0:
            last_row = df.iloc[-1]
            price = last_row["close"]
            date = last_row["date"]
            ret = (price - position["entry_price"]) / position["entry_price"]
            exit_date = str(date.date()) if hasattr(date, "date") else str(date)
            try:
                holding_days = (pd.Timestamp(exit_date) - pd.Timestamp(position["entry_date"])).days
            except Exception:
                holding_days = 0

            trades.append({
                "entry_date": position["entry_date"],
                "exit_date": exit_date,
                "entry_price": position["entry_price"],
                "exit_price": price,
                "return": round(ret, 4),
                "holding_days": holding_days,
                "shares": position["shares"],
                "note": "forced_close",
            })

        return trades

    def _build_equity_curve(
        self, df: pd.DataFrame, trades: list[dict], capital: float
    ) -> list[dict]:
        """Build daily equity curve."""
        equity = capital
        curve = []
        trade_idx = 0
        in_position = False
        entry_price = 0
        shares = 0

        for i in range(len(df)):
            row = df.iloc[i]
            date = str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])

            # Check if we enter a position today
            if trade_idx < len(trades) and trades[trade_idx]["entry_date"] == date:
                in_position = True
                entry_price = trades[trade_idx]["entry_price"]
                shares = trades[trade_idx]["shares"]

            # Check if we exit today
            if trade_idx < len(trades) and trades[trade_idx]["exit_date"] == date and in_position:
                exit_price = trades[trade_idx]["exit_price"]
                equity += shares * (exit_price - entry_price)
                in_position = False
                trade_idx += 1

            # Mark-to-market
            if in_position:
                mtm = equity + shares * (row["close"] - entry_price)
            else:
                mtm = equity

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
        }
