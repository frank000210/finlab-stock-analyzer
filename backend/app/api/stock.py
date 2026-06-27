"""Stock data API endpoints."""

from fastapi import APIRouter, Query, HTTPException
from datetime import date, timedelta
from ..crawler import StockPriceCrawler, FinMindClient

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    """Search stocks by symbol or name."""
    try:
        client = FinMindClient()
        df = await client.get_stock_info()
        if df.empty:
            return {"success": True, "data": {"items": []}}

        # Filter by query
        mask = (
            df["stock_id"].str.contains(q, case=False, na=False) |
            df.get("stock_name", df.get("Industry_category", "")).str.contains(q, case=False, na=False)
        )
        filtered = df[mask].head(20)

        items = []
        for _, row in filtered.iterrows():
            items.append({
                "symbol": row.get("stock_id", ""),
                "name_zh": row.get("stock_name", ""),
                "market": row.get("type", "TWSE"),
                "industry": row.get("Industry_category", ""),
            })

        return {"success": True, "data": {"items": items}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/info")
async def get_stock_info(symbol: str):
    """Get stock basic info."""
    try:
        client = FinMindClient()
        df = await client.get_stock_info()
        if df.empty:
            raise HTTPException(status_code=404, detail="Stock not found")

        row = df[df["stock_id"] == symbol]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

        row = row.iloc[0]
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "name_zh": row.get("stock_name", ""),
                "market": row.get("type", "TWSE"),
                "industry": row.get("Industry_category", ""),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/price")
async def get_stock_price(
    symbol: str,
    start: date = Query(default=None),
    end: date = Query(default=None),
    period: str = Query(default="1d", pattern="^(1d|1w|1mo)$"),
):
    """Get historical OHLCV data."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=365)

    try:
        crawler = StockPriceCrawler()
        df = await crawler.get_price(symbol, str(start), str(end), period)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

        items = []
        for _, row in df.iterrows():
            items.append({
                "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            })

        return {
            "success": True,
            "data": {"symbol": symbol, "period": period, "items": items},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
