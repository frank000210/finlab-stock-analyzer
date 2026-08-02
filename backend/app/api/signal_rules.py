"""Signal rules API endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

from ..ai_agent.signal_generator import build_market_snapshot
from ..signal_rules.engine import SignalRuleCreate, SignalRuleUpdate, rule_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/signal-rules", tags=["signal-rules"])

# MM1：create/update/delete/activate 這四支端點都沒有掛驗證（跟 FF1 的
# exec() 沙箱一樣，SignalRulesView.vue 是一般使用者功能，不能加
# require_admin）。但 rule_engine 是整個行程共用的單例、沒有任何 per-user
# 區隔——GET 列表本身也沒驗證，任何人都看得到所有規則 ID，代表這四支端點
# 合起來等於「任何匿名訪客都能無限次頂替/刪除全站唯一的作用中規則」，會
# 直接反映在 GET /api/v1/trade/pending 顯示給所有訪客的訊號上。無法比照
# 加驗證，改用跟 LL1/LL3 一致的節流機制擋自動化濫用。
_RULES_WINDOW_MINUTES = 10
_RULES_MAX_CALLS = 20


async def _check_signal_rules_rate_limit(request: Request) -> None:
    from ..api.analytics import _get_client_ip
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    try:
        count = await increment_rate_limit(f"signal_rules_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _RULES_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"規則異動請求過於頻繁，請 {_RULES_WINDOW_MINUTES} 分鐘後再試。",
        )


class SignalRuleTestRequest(BaseModel):
    id: str | None = None
    symbol: str = "2330"
    script: str | None = None


@router.get("")
async def list_signal_rules():
    return {"success": True, "data": {"items": [rule.model_dump() for rule in rule_engine.list_rules()]}}


@router.post("", dependencies=[Depends(_check_signal_rules_rate_limit)])
async def create_signal_rule(payload: SignalRuleCreate = Body(...)):
    try:
        rule = await rule_engine.create_rule(payload)
        return {"success": True, "data": rule.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("create_signal_rule failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{id}", dependencies=[Depends(_check_signal_rules_rate_limit)])
async def update_signal_rule(id: str, payload: SignalRuleUpdate = Body(...)):
    try:
        rule = await rule_engine.update_rule(id, payload)
        return {"success": True, "data": rule.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("update_signal_rule failed for %s", id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{id}", dependencies=[Depends(_check_signal_rules_rate_limit)])
async def delete_signal_rule(id: str):
    try:
        await rule_engine.delete_rule(id)
        return {"success": True, "data": {"deleted": id}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("delete_signal_rule failed for %s", id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{id}/activate", dependencies=[Depends(_check_signal_rules_rate_limit)])
async def activate_signal_rule(id: str):
    try:
        rule = await rule_engine.activate_rule(id)
        return {"success": True, "data": rule.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("activate_signal_rule failed for %s", id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test", dependencies=[Depends(_check_signal_rules_rate_limit)])
async def test_signal_rule(payload: SignalRuleTestRequest = Body(...)):
    try:
        snapshot = await build_market_snapshot(payload.symbol)
        loop = asyncio.get_event_loop()
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
                result = await loop.run_in_executor(None, rule_engine.execute_rule, temp_rule.id, snapshot)
            finally:
                await rule_engine.delete_rule(temp_rule.id)
        elif payload.id:
            result = await loop.run_in_executor(None, rule_engine.execute_rule, payload.id, snapshot)
        else:
            active_id = rule_engine.get_active_rule().id
            result = await loop.run_in_executor(None, rule_engine.execute_rule, active_id, snapshot)
        return {"success": True, "data": result.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("test_signal_rule failed for %s", payload.symbol)
        raise HTTPException(status_code=500, detail=str(exc))
