"""AI agent API endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..ai_agent import DEFAULT_SYMBOLS, generate_signals, get_alpha_scores
from ..signal_rules import rule_engine

router = APIRouter(prefix="/api/v1/agent", tags=["ai-agent"])


@router.get("/signals")
async def get_agent_signals(
    type: Literal["ALL", "BUY", "SELL", "HOLD"] = Query(default="ALL"),
    ruleId: str = Query(default="default"),
    symbols: str | None = Query(default=None),
):
    try:
        target_symbols = [item.strip() for item in symbols.split(",")] if symbols else DEFAULT_SYMBOLS
        items = await generate_signals(symbols=target_symbols, signal_type=type, rule_id=ruleId)
        return {"success": True, "data": {"items": [item.model_dump() for item in items]}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/alpha-scores")
async def get_agent_alpha_scores(
    ruleId: str = Query(default="default"),
    symbols: str | None = Query(default=None),
):
    try:
        target_symbols = [item.strip() for item in symbols.split(",")] if symbols else DEFAULT_SYMBOLS
        scores = await get_alpha_scores(symbols=target_symbols, rule_id=ruleId)
        return {"success": True, "data": {"items": scores}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/active-rule")
async def get_active_rule():
    try:
        return {"success": True, "data": rule_engine.get_active_rule().model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
