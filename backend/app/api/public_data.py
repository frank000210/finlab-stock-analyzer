"""Public-data API endpoints."""

from fastapi import APIRouter

from ..crawler.twse_public import TwsePublicCrawler

router = APIRouter(prefix="/api/v1/stocks", tags=["public-data"])


@router.get("/{symbol}/public-data")
async def get_public_data(symbol: str):
    crawler = TwsePublicCrawler()
    data = await crawler.get_public_data(symbol)
    return {"success": True, "data": data}
