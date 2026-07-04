"""FinMind API Client - Primary data source for Taiwan stock market."""

import hashlib
import time

import httpx
import pandas as pd
from typing import Optional
from ..config.settings import get_settings


# Module-level cache: { cache_key: (timestamp, dataframe) }
_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_CACHE_TTL = 300  # 5 minutes


def _clear_cache() -> int:
    count = len(_cache)
    _cache.clear()
    return count


try:
    from ..db.memory_cache import register as _register_memory_cache

    _register_memory_cache("finmind", lambda: len(_cache), _clear_cache)
except Exception:  # registry 不可用時不影響本模組運作
    pass


def _make_cache_key(dataset: str, params: dict) -> str:
    """Create a deterministic cache key from dataset + params."""
    key_str = dataset + "|" + "|".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "token")
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_cached(key: str) -> pd.DataFrame | None:
    """Return cached DataFrame if still valid, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, df = entry
    if time.time() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return df


def _set_cached(key: str, df: pd.DataFrame) -> None:
    """Store DataFrame in cache."""
    _cache[key] = (time.time(), df)
    # Evict old entries if cache grows too large (>200 entries)
    if len(_cache) > 200:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]


class FinMindClient:
    """Wrapper for FinMind Trade API."""

    BASE_URL = "https://api.finmindtrade.com/api/v4/data"

    def __init__(self, token: Optional[str] = None):
        self.token = token or get_settings().finmind_token

    async def _fetch(self, dataset: str, params: dict) -> pd.DataFrame:
        """Generic async fetch from FinMind API with caching."""
        cache_key = _make_cache_key(dataset, params)
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached.copy()

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

        df = pd.DataFrame(data.get("data", []))
        _set_cached(cache_key, df)
        return df

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

    async def get_dividend_history(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch dividend history."""
        return await self._fetch(
            "TaiwanStockDividend",
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
