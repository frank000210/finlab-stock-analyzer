"""Public-data API endpoints."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request

from ..crawler.twse_public import TwsePublicCrawler

router = APIRouter(prefix="/api/v1/stocks", tags=["public-data"])
logger = logging.getLogger(__name__)

# OO9: same vulnerability class as JJ5 (social_buzz.py) -- get_public_data()
# fans out to 4 concurrent external scrapes (MOPS/TWSE/FinMind) per call, and
# the in-process cache key is the raw symbol string with no format check, so
# varying the symbol on every request bypasses the cache entirely and forces
# a fresh scrape every time (risking the shared outbound IP getting blocked,
# same concern as JJ5).
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")
_PUBLIC_DATA_WINDOW_MINUTES = 10
_PUBLIC_DATA_MAX_CALLS = 60


async def _check_public_data_rate_limit(request: Request) -> None:
    from ..api.analytics import _get_client_ip
    from ..db.cache import increment_rate_limit

    ip = _get_client_ip(request)
    if not ip or ip == "unknown":
        return
    try:
        count = await increment_rate_limit(f"public_data_rate:{ip}", "rate_limit")
    except Exception:
        return
    if count > _PUBLIC_DATA_MAX_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"查詢過於頻繁，請 {_PUBLIC_DATA_WINDOW_MINUTES} 分鐘後再試。",
        )


@router.get("/{symbol}/public-data", dependencies=[Depends(_check_public_data_rate_limit)])
async def get_public_data(symbol: str):
    if not _SYMBOL_RE.match(symbol):
        raise HTTPException(status_code=400, detail="不支援的股票代碼格式。")
    crawler = TwsePublicCrawler()
    data = await crawler.get_public_data(symbol)
    return {"success": True, "data": data}
