"""Human-in-the-loop trade approval service."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from ..ai_agent.signal_generator import SignalItem, generate_signals
from ..risk.manager import risk_manager


class PendingTrade(BaseModel):
    task_id: str
    symbol: str
    type: Literal["BUY", "SELL"]
    confidence: float = Field(ge=0.0, le=1.0)
    quantity: int = Field(gt=0)
    estimated_price: float = Field(gt=0.0)
    reasoning: str
    created_at: datetime
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"


class TradeApprovalAction(BaseModel):
    task_id: str
    action: Literal["APPROVE", "REJECT"]


class TradeApprovalService:
    def __init__(self) -> None:
        self._trades: dict[str, PendingTrade] = {}

    async def sync_from_signals(self, rule_id: str = "default") -> list[PendingTrade]:
        signals = await generate_signals(rule_id=rule_id)
        for signal in signals:
            if signal.signal not in {"BUY", "SELL"} or signal.confidence <= 0.7:
                continue
            if self._existing_open_trade(signal):
                continue
            pending = PendingTrade(
                task_id=str(uuid4()),
                symbol=signal.symbol,
                type=signal.signal,
                confidence=signal.confidence,
                quantity=self._infer_quantity(signal),
                estimated_price=signal.price,
                reasoning=signal.reasoning,
                created_at=datetime.utcnow(),
            )
            self._trades[pending.task_id] = pending
        return list(self._trades.values())

    async def list_pending(self, status: str = "ALL", rule_id: str = "default") -> list[PendingTrade]:
        await self.sync_from_signals(rule_id=rule_id)
        items = list(self._trades.values())
        if status == "ALL":
            return sorted(items, key=lambda trade: trade.created_at, reverse=True)
        return sorted(
            [trade for trade in items if trade.status == status],
            key=lambda trade: trade.created_at,
            reverse=True,
        )

    def approve_or_reject(self, action: TradeApprovalAction) -> PendingTrade:
        trade = self._trades.get(action.task_id)
        if not trade:
            raise ValueError(f"Trade task {action.task_id} not found")
        trade.status = "APPROVED" if action.action == "APPROVE" else "REJECTED"
        self._trades[action.task_id] = trade
        if trade.status == "APPROVED":
            risk_manager.record_trade()
        return trade

    def _existing_open_trade(self, signal: SignalItem) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=1)
        for trade in self._trades.values():
            if (
                trade.symbol == signal.symbol
                and trade.type == signal.signal
                and trade.created_at >= cutoff
            ):
                return True
        return False

    @staticmethod
    def _infer_quantity(signal: SignalItem) -> int:
        if signal.price <= 0:
            return 1
        nominal_budget = 100_000
        quantity = int(nominal_budget // max(signal.price, 1))
        return max(quantity, 1)


trade_approval_service = TradeApprovalService()
