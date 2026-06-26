"""FinMind API Client - Primary data source for Taiwan stock market."""

import httpx
import pandas as pd
from typing import Optional
from ..config.settings import get_settings


class FinMindClient:
    """Wrapper for FinMind Trade API."""

    BASE_URL = "https://api.finmindtrade.com/api/v4/data"

    def __init__(self, token: Optional[str] = None):
        self.token = token or get_settings().finmind_token

    async def _fetch(self, dataset: str, params: dict) -> pd.DataFrame:
        """Generic async fetch from FinMind API."""
        payload = {
            "dataset": dataset,
            "token": self.token,
            **params,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self.BASE_URL, params=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != 200:
            raise ValueError(f"FinMind API error: {data.get('msg', 'Unknown')}")

        return pd.DataFrame(data.get("data", []))

    async def get_stock_price(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch daily OHLCV data."""
        df = await self._fetch(
            "TaiwanStockPrice",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )
        if df.empty:
            return df
        df = df.rename(columns={
            "date": "date",
            "open": "open",
            "max": "high",
            "min": "low",
            "close": "close",
            "Trading_Volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "open", "high", "low", "close", "volume"]]

    async def get_institutional_investors(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch institutional investor buy/sell data."""
        return await self._fetch(
            "TaiwanStockInstitutionalInvestorsBuySell",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_monthly_revenue(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch monthly revenue data."""
        return await self._fetch(
            "TaiwanStockMonthRevenue",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_financial_statements(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch quarterly financial statements."""
        return await self._fetch(
            "TaiwanStockFinancialStatements",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_shareholding(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch shareholding distribution."""
        return await self._fetch(
            "TaiwanStockHoldingSharesPer",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_margin_trading(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch margin trading data (融資融券)."""
        return await self._fetch(
            "TaiwanStockMarginPurchaseShortSale",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_stock_info(self) -> pd.DataFrame:
        """Fetch all Taiwan stock info for search."""
        return await self._fetch("TaiwanStockInfo", {})
