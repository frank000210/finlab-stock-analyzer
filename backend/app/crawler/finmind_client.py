"""FinMind API Client - Primary data source for Taiwan stock market."""

import asyncio
import hashlib
import logging
import time

import httpx
import pandas as pd
from typing import Optional
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

# Module-level cache: { cache_key: (timestamp, dataframe) }
_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_CACHE_TTL = 300  # 5 minutes

# TaiwanStockInfo 專用長效快取（全市場名單日頻變動極小，避免跨頁反覆消耗額度）
_stock_info_mem: tuple[float, pd.DataFrame] | None = None
_STOCK_INFO_MEM_TTL = 3600  # 程序內 60 分鐘
_STOCK_INFO_CACHE_KEY = "finmind:stock_info:v1"
_STOCK_INFO_STALE_KEY = "finmind:stock_info:stale:v1"
_STOCK_INFO_MONGO_TIMEOUT = 1.5
_STOCK_INFO_MONGO_COOLDOWN_SEC = 30.0
_stock_info_mongo_cooldown_until: float = 0.0

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
    global _stock_info_mem, _stock_info_mongo_cooldown_until
    count = len(_cache) + (1 if _stock_info_mem is not None else 0)
    _cache.clear()
    _stock_info_mem = None
    _stock_info_mongo_cooldown_until = 0.0
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

    def __init__(self, token: Optional[str] = None, use_local_db: bool = True):
        self.token = token or get_settings().finmind_token
        self.use_local_db = use_local_db
        # 追蹤最近一次查詢實際命中的資料源（例如 'md_price' / 'od_margin' / 'md+od_margin' / 'finmind'）
        self.last_read_source: Optional[str] = None

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
        """Fetch daily OHLCV data（優先讀本地 md_price，涵蓋不足再回落 FinMind）."""
        self.last_read_source = None
        if self.use_local_db:
            from ..data.db_reader import read_stock_price_with_source

            local_df, src = await read_stock_price_with_source(symbol, start, end)
            if local_df is not None and not local_df.empty:
                self.last_read_source = src
                return local_df

        df = await self._fetch(
            "TaiwanStockPrice",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )
        self.last_read_source = "finmind"
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
        """Fetch institutional investor buy/sell data（優先讀本地 md_institutional）."""
        self.last_read_source = None
        if self.use_local_db:
            from ..data.db_reader import read_institutional_with_source

            local_df, src = await read_institutional_with_source(symbol, start, end)
            if local_df is not None and not local_df.empty:
                self.last_read_source = src
                return local_df

        self.last_read_source = "finmind"
        return await self._fetch(
            "TaiwanStockInstitutionalInvestorsBuySell",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_monthly_revenue(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch monthly revenue data（優先讀本地 md_revenue → od_revenue）."""
        self.last_read_source = None
        if self.use_local_db:
            from ..data.db_reader import read_monthly_revenue_with_source

            local_df, src = await read_monthly_revenue_with_source(symbol, start, end)
            if local_df is not None and not local_df.empty:
                self.last_read_source = src
                return local_df

        self.last_read_source = "finmind"
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

    async def get_balance_sheet(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch quarterly balance sheet（資產負債表）。

        欄位是長表：type（如 TotalAssets、Liabilities、Equity、
        EquityAttributableToOwnersOfParent）＋ value；FinMind 的綜合損益表
        （get_financial_statements）沒有負債比，負債比要用這支算。
        """
        return await self._fetch(
            "TaiwanStockBalanceSheet",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_cash_flows(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch cash-flow statement（現金流量表；金額為當年度累計，非單季）。"""
        return await self._fetch(
            "TaiwanStockCashFlowsStatement",
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

    async def get_dividend_result(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """Fetch ex-dividend results (per ex-date: 除息前收盤、除息參考價、每股現金股利).

        Unlike TaiwanStockDividend this carries the actual ex-date and the
        before/reference prices, which is what 填息 and total-return adjustment need.
        """
        return await self._fetch(
            "TaiwanStockDividendResult",
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
        """Fetch margin trading data (融資融券；優先讀本地 md_margin → od_margin)."""
        self.last_read_source = None
        if self.use_local_db:
            from ..data.db_reader import read_margin_trading_with_source

            local_df, src = await read_margin_trading_with_source(symbol, start, end)
            if local_df is not None and not local_df.empty:
                self.last_read_source = src
                return local_df

        self.last_read_source = "finmind"
        return await self._fetch(
            "TaiwanStockMarginPurchaseShortSale",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def get_futures_institutional(
        self, futures_id: str, start: str, end: str
    ) -> pd.DataFrame:
        """期貨三大法人多空部位（V1 大盤多空儀表板用）：台指期 data_id='TX'，
        含多/空方交易與未平倉的口數與金額。金額單位為千元。
        """
        return await self._fetch(
            "TaiwanFuturesInstitutionalInvestors",
            {"data_id": futures_id, "start_date": start, "end_date": end},
        )

    async def get_total_margin(self, start: str, end: str) -> pd.DataFrame:
        """全市場融資融券餘額（V1 大盤多空儀表板用）：name 欄位區分
        MarginPurchaseMoney（融資金額）等類型，餘額單位為元。
        """
        return await self._fetch(
            "TaiwanStockTotalMarginPurchaseShortSale",
            {"start_date": start, "end_date": end},
        )

    async def get_valuation(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """估值資料（U1 同業比較與評分卡用）：交易所計算的本益比 PER、股價淨值比
        PBR、殖利率 dividend_yield，日頻。虧損股 PER 會缺值或為 0。
        優先讀本地 md_valuation → od_valuation，涵蓋不足再回落 FinMind。
        """
        self.last_read_source = None
        if self.use_local_db:
            from ..data.db_reader import read_valuation_with_source

            local_df, src = await read_valuation_with_source(symbol, start, end)
            if local_df is not None and not local_df.empty:
                self.last_read_source = src
                return local_df

        self.last_read_source = "finmind"
        return await self._fetch(
            "TaiwanStockPER",
            {"data_id": symbol, "start_date": start, "end_date": end},
        )

    async def _read_stock_info_mongo(self, key: str) -> pd.DataFrame | None:
        global _stock_info_mongo_cooldown_until
        if time.monotonic() < _stock_info_mongo_cooldown_until:
            return None
        try:
            from ..db.cache import get_cache

            records = await asyncio.wait_for(get_cache(key), timeout=_STOCK_INFO_MONGO_TIMEOUT)
            if isinstance(records, list) and records:
                return pd.DataFrame(records)
        except Exception as exc:  # noqa: BLE001
            _stock_info_mongo_cooldown_until = time.monotonic() + _STOCK_INFO_MONGO_COOLDOWN_SEC
            logger.debug("get_stock_info mongo read skipped (%s): %s", key, exc)
        return None

    async def _write_stock_info_mongo(self, df: pd.DataFrame) -> None:
        global _stock_info_mongo_cooldown_until
        if df is None or df.empty or time.monotonic() < _stock_info_mongo_cooldown_until:
            return
        try:
            from ..db.cache import set_cache

            records = df.to_dict("records")
            await asyncio.wait_for(
                set_cache(_STOCK_INFO_CACHE_KEY, records, "stock_info"),
                timeout=_STOCK_INFO_MONGO_TIMEOUT,
            )
            await asyncio.wait_for(
                set_cache(_STOCK_INFO_STALE_KEY, records, "stock_info_stale"),
                timeout=_STOCK_INFO_MONGO_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            _stock_info_mongo_cooldown_until = time.monotonic() + _STOCK_INFO_MONGO_COOLDOWN_SEC
            logger.debug("get_stock_info mongo write skipped: %s", exc)

    async def get_stock_info(self) -> pd.DataFrame:
        """Fetch all Taiwan stock info for search.

        快取階層：程序內 60 分鐘 → MongoDB 24 小時 → FinMind API；
        若 FinMind 失敗（例如額度耗盡），自動回退至過期舊表（程序內或 Mongo 7 天副本）。
        """
        global _stock_info_mem
        self.last_read_source = None
        now = time.time()

        # 1. 程序內新鮮快取（60 分鐘）
        if _stock_info_mem is not None:
            ts, mem_df = _stock_info_mem
            if now - ts <= _STOCK_INFO_MEM_TTL and not mem_df.empty:
                self.last_read_source = "memory_stock_info"
                return mem_df.copy()

        # 2. MongoDB 24 小時快取
        if self.use_local_db:
            mongo_df = await self._read_stock_info_mongo(_STOCK_INFO_CACHE_KEY)
            if mongo_df is not None and not mongo_df.empty:
                _stock_info_mem = (now, mongo_df)
                self.last_read_source = "mongo_stock_info"
                return mongo_df.copy()

        # 3. 回落 FinMind API；失敗時安全回退過期舊表
        try:
            df = await self._fetch("TaiwanStockInfo", {})
            self.last_read_source = "finmind"
            if df is not None and not df.empty:
                _stock_info_mem = (now, df.copy())
                if self.use_local_db:
                    await self._write_stock_info_mongo(df)
            return df
        except Exception as exc:
            if _stock_info_mem is not None and not _stock_info_mem[1].empty:
                logger.warning("get_stock_info failed (%s); falling back to stale in-memory table", exc)
                self.last_read_source = "stale_stock_info"
                return _stock_info_mem[1].copy()
            if self.use_local_db:
                stale_df = await self._read_stock_info_mongo(_STOCK_INFO_STALE_KEY)
                if stale_df is not None and not stale_df.empty:
                    logger.warning("get_stock_info failed (%s); falling back to stale Mongo table", exc)
                    _stock_info_mem = (now - _STOCK_INFO_MEM_TTL - 1, stale_df)
                    self.last_read_source = "stale_stock_info"
                    return stale_df.copy()
            raise
