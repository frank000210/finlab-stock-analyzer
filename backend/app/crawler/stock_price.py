"""Stock price crawler with FinMind primary and yfinance fallback."""

import logging

import pandas as pd
import yfinance as yf
from typing import Optional
from .finmind_client import FinMindClient

logger = logging.getLogger(__name__)


class StockPriceCrawler:
    """Fetches stock price data with fallback mechanism.

    資料血統（A2）：`last_source` 記錄最近一次 get_price 實際使用的來源
    （'finmind' 主源 / 'yfinance' 備援 / None 無資料），API 層可回傳給前端
    標示。crawler 實例為 per-request，無共享狀態問題。
    """

    def __init__(self, finmind_token: Optional[str] = None):
        self.finmind = FinMindClient(token=finmind_token)
        self.last_source: Optional[str] = None

    async def get_price(
        self, symbol: str, start: str, end: str, period: str = "1d"
    ) -> pd.DataFrame:
        """Get OHLCV data. Tries FinMind first, falls back to yfinance."""
        self.last_source = None
        try:
            df = await self.finmind.get_stock_price(symbol, start, end)
            if not df.empty:
                if period == "1w":
                    df = self._resample(df, "W")
                elif period == "1mo":
                    df = self._resample(df, "ME")
                self.last_source = "finmind"
                return df
        except Exception as e:
            logger.warning("FinMind price fetch failed for %s (%s~%s): %s", symbol, start, end, e)

        # Fallback to yfinance
        df = self._fetch_yfinance(symbol, start, end, period)
        if not df.empty:
            self.last_source = "yfinance"
        return df

    def _fetch_yfinance(
        self, symbol: str, start: str, end: str, period: str
    ) -> pd.DataFrame:
        """Fetch from Yahoo Finance as fallback."""
        ticker = f"{symbol}.TW"
        interval_map = {"1d": "1d", "1w": "1wk", "1mo": "1mo"}
        interval = interval_map.get(period, "1d")

        df = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=False)
        if df.empty:
            # Try .TWO for OTC stocks
            ticker = f"{symbol}.TWO"
            df = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=False)

        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        return df[["date", "open", "high", "low", "close", "volume"]]

    def _resample(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """Resample daily data to weekly/monthly."""
        df = df.set_index("date")
        resampled = df.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()
        return resampled.reset_index()
