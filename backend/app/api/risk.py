"""Risk control API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..risk import risk_manager

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/status")
async def get_risk_status():
    try:
        return {"success": True, "data": risk_manager.get_status().model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/equity-curve")
async def get_equity_curve(hours: int = Query(default=30, ge=1, le=720)):
    try:
        points = risk_manager.get_equity_curve(hours=hours)
        return {"success": True, "data": {"items": [point.model_dump() for point in points]}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker():
    try:
        status = risk_manager.reset_circuit_breaker()
        return {"success": True, "data": status.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
