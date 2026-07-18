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

# P2：共用一個 httpx.AsyncClient（含連線池），不要每次 _fetch() 都開一個新的。
# 觀察清單掃描一次可能對 30 檔股票各發 1-2 個 FinMind 請求、併發觸發，若每次
# 都重新 TCP+TLS 握手，額外開銷會被併發數放大。行程關閉時由 main.py 的
# lifespan shutdown 呼叫 close_finmind_client() 釋放。
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def close_finmind_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


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
        client = _get_client()
        resp = await client.get(self.BASE_URL, params=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # httpx's default exception message (and str(exc)) embeds the
            # full request URL, which includes our FINMIND_TOKEN as a
            # query param. API route handlers across this codebase
            # commonly return str(e) as the HTTP error detail, so letting
            # the original exception propagate would leak the token to
            # any caller whenever FinMind returns a 4xx/5xx.
            raise ValueError(
                f"FinMind request failed: HTTP {exc.response.status_code}"
            ) from None
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

    async def get_shares_outstanding(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """已發行股數（含外資持股比例），用來算市值＝現價×已發行股數。

        跟 get_shareholding()（股權分散表 TaiwanStockHoldingSharesPer）是不同的
        FinMind dataset：這支是 TaiwanStockShareholding，免費/現有付費等級都能
        存取（跟需要額外升級的 TaiwanStockMarketValue 不同）。
        """
        return await self._fetch(
            "TaiwanStockShareholding",
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

    async def get_valuation(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """估值資料（U1 同業比較用）：交易所計算的本益比 PER、股價淨值比
        PBR、殖利率 dividend_yield，日頻。虧損股 PER 會缺值或為 0。
        """
        return await self._fetch(
            "TaiwanStockPER",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_stock_info(self) -> pd.DataFrame:
        """Fetch all Taiwan stock info for search."""
        return await self._fetch("TaiwanStockInfo", {})
