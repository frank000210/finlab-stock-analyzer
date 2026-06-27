"""Trade approval API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from ..signal_rules import rule_engine
from ..trade.approval import TradeApprovalAction, trade_approval_service

router = APIRouter(prefix="/api/v1/trade", tags=["trade"])


@router.get("/pending")
async def get_pending_trades(status: str = Query(default="ALL")):
    try:
        active_rule = rule_engine.get_active_rule()
        items = await trade_approval_service.list_pending(status=status.upper(), rule_id=active_rule.id)
        return {"success": True, "data": {"items": [item.model_dump() for item in items]}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/approve")
async def approve_trade(payload: TradeApprovalAction = Body(...)):
    try:
        trade = trade_approval_service.approve_or_reject(payload)
        return {"success": True, "data": trade.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
