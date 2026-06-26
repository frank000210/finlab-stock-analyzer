"""Analysis API endpoints."""

from fastapi import APIRouter, Query, HTTPException
from datetime import date, timedelta
from ..crawler import StockPriceCrawler, FundamentalCrawler, InstitutionalCrawler
from ..analysis import TechnicalAnalyzer

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get("/{symbol}/technical")
async def get_technical_analysis(
    symbol: str,
    indicators: str = Query(default="ma,bollinger,macd,kd,rsi,volume"),
    start: date = Query(default=None),
    end: date = Query(default=None),
    period: str = Query(default="1d"),
):
    """Get technical indicators for a stock."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=365)

    try:
        crawler = StockPriceCrawler()
        df = await crawler.get_price(symbol, str(start), str(end), period)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        analyzer = TechnicalAnalyzer()
        ind_list = [i.strip() for i in indicators.split(",")]
        computed = analyzer.compute(df, ind_list)
        latest = analyzer.get_latest_indicators(df, ind_list)

        # Build series
        series = []
        for _, row in computed.iterrows():
            entry = {
                "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            }
            for col in computed.columns:
                if col not in ["date", "open", "high", "low", "close", "volume"]:
                    val = row[col]
                    if val is not None and not (isinstance(val, float) and val != val):
                        entry[col] = round(float(val), 2)
            series.append(entry)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "indicators": latest,
                "series": series,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/fundamental")
async def get_fundamental(
    symbol: str,
    metrics: str = Query(default="revenue,eps,margins,debt_ratios"),
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Get fundamental data."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=365 * 3)

    try:
        crawler = FundamentalCrawler()
        result = {}

        metric_list = [m.strip() for m in metrics.split(",")]

        if "revenue" in metric_list:
            result["revenue_monthly"] = await crawler.get_monthly_revenue(
                symbol, str(start), str(end)
            )

        if any(m in metric_list for m in ["eps", "margins", "debt_ratios"]):
            financials = await crawler.get_financial_statements(
                symbol, str(start), str(end)
            )
            if "eps" in metric_list:
                result["eps_quarterly"] = financials["eps_quarterly"]
            if "margins" in metric_list:
                result["margins"] = financials["margins"]
            if "debt_ratios" in metric_list:
                result["debt_ratios"] = financials["debt_ratios"]

        return {"success": True, "data": {"symbol": symbol, **result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/chip")
async def get_chip_analysis(
    symbol: str,
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Get institutional investor (chip) analysis."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=90)

    try:
        crawler = InstitutionalCrawler()
        data = await crawler.get_chip_data(symbol, str(start), str(end))
        return {"success": True, "data": {"symbol": symbol, **data}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
