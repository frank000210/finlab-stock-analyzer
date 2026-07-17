"""Signal rules API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ..ai_agent.signal_generator import build_market_snapshot
from ..signal_rules.engine import SignalRuleCreate, SignalRuleUpdate, rule_engine

router = APIRouter(prefix="/api/v1/signal-rules", tags=["signal-rules"])


class SignalRuleTestRequest(BaseModel):
    id: str | None = None
    symbol: str = "2330"
    script: str | None = None


@router.get("")
async def list_signal_rules():
    return {"success": True, "data": {"items": [rule.model_dump() for rule in rule_engine.list_rules()]}}


@router.post("")
async def create_signal_rule(payload: SignalRuleCreate = Body(...)):
    try:
        rule = await rule_engine.create_rule(payload)
        return {"success": True, "data": rule.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{id}")
async def update_signal_rule(id: str, payload: SignalRuleUpdate = Body(...)):
    try:
        rule = await rule_engine.update_rule(id, payload)
        return {"success": True, "data": rule.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{id}")
async def delete_signal_rule(id: str):
    try:
        await rule_engine.delete_rule(id)
        return {"success": True, "data": {"deleted": id}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{id}/activate")
async def activate_signal_rule(id: str):
    try:
        rule = await rule_engine.activate_rule(id)
        return {"success": True, "data": rule.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test")
async def test_signal_rule(payload: SignalRuleTestRequest = Body(...)):
    try:
        snapshot = await build_market_snapshot(payload.symbol)
        if payload.script:
            temp_rule = await rule_engine.create_rule(
                SignalRuleCreate(
                    name="Ad-hoc test rule",
                    description="Temporary rule created by /test endpoint.",
                    script=payload.script,
                    isActive=False,
                )
            )
            try:
                result = rule_engine.execute_rule(temp_rule.id, snapshot)
            finally:
                await rule_engine.delete_rule(temp_rule.id)
        elif payload.id:
            result = rule_engine.execute_rule(payload.id, snapshot)
        else:
            result = rule_engine.execute_rule(rule_engine.get_active_rule().id, snapshot)
        return {"success": True, "data": result.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
