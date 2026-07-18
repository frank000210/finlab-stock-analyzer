"""同業比較 (Peer Comparison) API — U1."""

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ..analysis.peer_compare import build_comparison, get_peer_group, set_peer_group
from ..data.us_symbols import is_tw_symbol, normalize_symbol

router = APIRouter(prefix="/api/v1/stocks", tags=["peers"])


class PeerItem(BaseModel):
    symbol: str
    source: str = "manual"  # manual | ai | industry


class PeerGroupPayload(BaseModel):
    peers: list[PeerItem] = []


def _check_tw(symbol: str) -> str:
    symbol = normalize_symbol(symbol)
    if not is_tw_symbol(symbol):
        raise HTTPException(status_code=404, detail="同業比較僅支援台股")
    return symbol


@router.get("/{symbol}/peers")
async def list_peers(symbol: str):
    """生效中的同業群組（自訂優先，否則同產業依成交金額取前 5）。"""
    try:
        return {"success": True, "data": await get_peer_group(_check_tw(symbol))}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"同業群組查詢失敗：{exc}")


@router.put("/{symbol}/peers")
async def save_peers(symbol: str, payload: PeerGroupPayload = Body(...)):
    """儲存自訂同業群組；傳空清單＝清除自訂、回到產業預設。"""
    symbol = _check_tw(symbol)
    try:
        await set_peer_group(symbol, [p.model_dump() for p in payload.peers])
        return {"success": True, "data": await get_peer_group(symbol)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"同業群組儲存失敗：{exc}")


@router.get("/{symbol}/peer-comparison")
async def peer_comparison(symbol: str):
    """同業比較表：目標股＋同業的估值/成長/獲利/動能指標。"""
    try:
        return {"success": True, "data": await build_comparison(_check_tw(symbol))}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"同業比較查詢失敗：{exc}")
