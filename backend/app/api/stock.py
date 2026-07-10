"""Stock data API endpoints."""

from fastapi import APIRouter, Query, HTTPException
from datetime import date, timedelta
from ..crawler import StockPriceCrawler, FinMindClient

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    """Search stocks by symbol or name（台股 FinMind + 內建美股指數/龍頭）。

    使用者自己打 2330.TW / 2330.TWO 尾碼一樣查得到（先 normalize 再比對）。
    """
    from ..data.us_symbols import US_SYMBOLS, normalize_symbol

    normalized = normalize_symbol(q)
    if normalized != q.strip().upper():
        # 命中 2330.TW / 2330.TWO 這類明確尾碼樣式 -> 用剝除後的乾淨代號查
        q = normalized

    # 美股/指數：內建字典比對（代號前綴或名稱包含），放在最前面
    us_items = []
    qu = q.strip().upper()
    for sym, meta in US_SYMBOLS.items():
        if qu in sym or q.strip() in meta["name"]:
            us_items.append({
                "symbol": sym,
                "name_zh": meta["name"],
                "market": "us",
                "industry": meta["industry"],
            })
    us_items = us_items[:8]

    try:
        client = FinMindClient()
        df = await client.get_stock_info()
        if df.empty:
            return {"success": True, "data": {"items": us_items}}

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
                "industry": row.get("industry_category", row.get("Industry_category", "")),
            })

        return {"success": True, "data": {"items": (us_items + items)[:20]}}
    except HTTPException:
        raise
    except Exception:
        # FinMind 掛掉時至少回美股內建結果
        return {"success": True, "data": {"items": us_items}}


@router.get("/{symbol}/info")
async def get_stock_info(symbol: str):
    """Get stock basic info（台股 FinMind；美股/指數用內建字典）。

    使用者自己打 2330.TW / 2330.TWO 尾碼一樣查得到（先 normalize 再查）。
    """
    from ..data.us_symbols import US_SYMBOLS, is_tw_symbol, normalize_symbol

    sym_u = normalize_symbol(symbol)
    if not is_tw_symbol(sym_u):
        meta = US_SYMBOLS.get(sym_u)
        return {
            "success": True,
            "data": {
                "symbol": sym_u,
                "name_zh": meta["name"] if meta else sym_u,
                "market": "us",
                "industry": meta["industry"] if meta else "美股",
            },
        }

    try:
        client = FinMindClient()
        df = await client.get_stock_info()
        if df.empty:
            raise HTTPException(status_code=404, detail="Stock not found")

        row = df[df["stock_id"] == sym_u]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"Stock {sym_u} not found")

        row = row.iloc[0]
        return {
            "success": True,
            "data": {
                "symbol": sym_u,
                "name_zh": row.get("stock_name", ""),
                "market": row.get("type", "TWSE"),
                "industry": row.get("industry_category", row.get("Industry_category", "")),
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
    """Get historical OHLCV data。使用者自己打 .TW／.TWO 尾碼一樣查得到。"""
    from ..data.us_symbols import normalize_symbol

    symbol = normalize_symbol(symbol)
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
            "data": {
                "symbol": symbol,
                "period": period,
                "items": items,
                # 資料血統（A2）：實際來源與最後一筆資料日，供前端標示新鮮度
                "source": crawler.last_source,
                "as_of": items[-1]["date"] if items else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
