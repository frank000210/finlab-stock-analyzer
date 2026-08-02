"""Trade approval API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..signal_rules import rule_engine
from ..trade.approval import TradeApprovalAction, trade_approval_service
from .admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trade", tags=["trade"])


# RR1: 交易核准端點先前無任何認證，任何人可列出或核准 AI 交易提案。
@router.get("/pending", dependencies=[Depends(require_admin)])
async def get_pending_trades(status: str = Query(default="ALL")):
    try:
        active_rule = rule_engine.get_active_rule()
        items = await trade_approval_service.list_pending(status=status.upper(), rule_id=active_rule.id)
        return {"success": True, "data": {"items": [item.model_dump() for item in items]}}
    except Exception as exc:
        logger.exception("get_pending_trades failed (status=%s)", status)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/approve", dependencies=[Depends(require_admin)])
async def approve_trade(payload: TradeApprovalAction = Body(...)):
    try:
        trade = trade_approval_service.approve_or_reject(payload)
        return {"success": True, "data": trade.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("approve_trade failed")
        raise HTTPException(status_code=500, detail=str(exc))
