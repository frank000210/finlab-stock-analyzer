"""In-memory risk management utilities."""

from __future__ import annotations

from datetime import datetime, timedelta
from random import Random
from typing import Literal

from pydantic import BaseModel, Field


class EquityPoint(BaseModel):
    timestamp: datetime
    value: float = Field(gt=0)


class RiskStatus(BaseModel):
    mdd_percent: float
    daily_trades: int
    circuit_breaker: Literal["ACTIVE", "WARNING", "PAUSED"]
    portfolio_value: float


class RiskManager:
    def __init__(self) -> None:
        self._state = {
            "portfolio_value": 1_000_000.0,
            "daily_trades": 0,
            "current_trade_date": datetime.utcnow().date().isoformat(),
            "circuit_breaker": "ACTIVE",
            "equity_curve": [],
            "mdd_percent": 0.0,
        }
        self._seed = 20260627
        self._ensure_equity_curve(hours=30)

    def get_status(self) -> RiskStatus:
        self._reset_daily_counter_if_needed()
        self._ensure_equity_curve(hours=30)
        self._refresh_circuit_breaker()
        return RiskStatus(
            mdd_percent=round(float(self._state["mdd_percent"]), 2),
            daily_trades=int(self._state["daily_trades"]),
            circuit_breaker=self._state["circuit_breaker"],
            portfolio_value=round(float(self._state["portfolio_value"]), 2),
        )

    def get_equity_curve(self, hours: int = 30) -> list[EquityPoint]:
        self._ensure_equity_curve(hours=max(1, hours))
        self._refresh_circuit_breaker()
        curve = self._state["equity_curve"][-hours:]
        return [EquityPoint(**point) for point in curve]

    def reset_circuit_breaker(self) -> RiskStatus:
        self._state["daily_trades"] = 0
        self._state["circuit_breaker"] = "ACTIVE"
        self._state["mdd_percent"] = 0.0
        self._state["equity_curve"] = []
        self._ensure_equity_curve(hours=30)
        return self.get_status()

    def record_trade(self) -> RiskStatus:
        self._reset_daily_counter_if_needed()
        self._state["daily_trades"] += 1
        self._refresh_circuit_breaker()
        return self.get_status()

    def _reset_daily_counter_if_needed(self) -> None:
        today = datetime.utcnow().date().isoformat()
        if self._state["current_trade_date"] != today:
            self._state["current_trade_date"] = today
            self._state["daily_trades"] = 0

    def _ensure_equity_curve(self, hours: int) -> None:
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        curve: list[dict] = self._state["equity_curve"]
        target_count = max(hours, 2)

        if not curve:
            base_time = now - timedelta(hours=target_count - 1)
            value = self._state["portfolio_value"]
            curve.append({"timestamp": base_time, "value": round(value, 2)})

        rng = Random(self._seed)
        while len(curve) < target_count:
            last_point = curve[-1]
            next_time = last_point["timestamp"] + timedelta(hours=1)
            drift = rng.uniform(-0.0075, 0.009)
            next_value = max(100_000.0, last_point["value"] * (1 + drift))
            curve.append({"timestamp": next_time, "value": round(next_value, 2)})

        while curve and curve[-1]["timestamp"] < now:
            last_point = curve[-1]
            next_time = last_point["timestamp"] + timedelta(hours=1)
            if next_time > now:
                break
            drift = rng.uniform(-0.0075, 0.009)
            next_value = max(100_000.0, last_point["value"] * (1 + drift))
            curve.append({"timestamp": next_time, "value": round(next_value, 2)})

        self._state["equity_curve"] = curve[-max(hours, 30):]
        self._state["portfolio_value"] = float(self._state["equity_curve"][-1]["value"])
        self._state["mdd_percent"] = self._calculate_mdd(self._state["equity_curve"])

    def _refresh_circuit_breaker(self) -> None:
        mdd = float(self._state["mdd_percent"])
        trades = int(self._state["daily_trades"])
        if mdd >= 10 or trades >= 20:
            status = "PAUSED"
        elif mdd >= 6 or trades >= 12:
            status = "WARNING"
        else:
            status = "ACTIVE"
        self._state["circuit_breaker"] = status

    @staticmethod
    def _calculate_mdd(curve: list[dict]) -> float:
        peak = 0.0
        max_drawdown = 0.0
        for point in curve:
            value = float(point["value"])
            if value > peak:
                peak = value
            if peak > 0:
                drawdown = (peak - value) / peak * 100
                max_drawdown = max(max_drawdown, drawdown)
        return round(max_drawdown, 2)


risk_manager = RiskManager()
