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
        """Get OHLCV data.

        台股（純數字代號）：FinMind 主源 → yfinance(.TW/.TWO) 備援。使用者
        自己打 .TW／.TWO 尾碼也視為同一檔（normalize_symbol 先剝除）。
        美股/指數（字母或 ^ 開頭，如 AAPL、^GSPC）：FinMind 沒有資料，
        直接走 yfinance 原始代號。
        """
        from ..data.us_symbols import is_tw_symbol, normalize_symbol

        self.last_source = None
        symbol = normalize_symbol(symbol)

        if is_tw_symbol(symbol):
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

        # yfinance：台股備援（.TW/.TWO）或美股直查
        df = self._fetch_yfinance(symbol, start, end, period)
        if not df.empty:
            self.last_source = "yfinance"
        return df

    def _fetch_yfinance(
        self, symbol: str, start: str, end: str, period: str
    ) -> pd.DataFrame:
        """Fetch from Yahoo Finance（台股備援加 .TW/.TWO；美股/指數用原始代號）。"""
        from ..data.us_symbols import is_tw_symbol

        interval_map = {"1d": "1d", "1w": "1wk", "1mo": "1mo"}
        interval = interval_map.get(period, "1d")

        if is_tw_symbol(symbol):
            df = yf.download(f"{symbol}.TW", start=start, end=end, interval=interval, progress=False, auto_adjust=False)
            if df.empty:
                # Try .TWO for OTC stocks
                df = yf.download(f"{symbol}.TWO", start=start, end=end, interval=interval, progress=False, auto_adjust=False)
        else:
            df = yf.download(symbol, start=start, end=end, interval=interval, progress=False, auto_adjust=False)

        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        # 指數的 volume 可能為 NaN → 補 0，避免 int() 轉換爆掉
        df["volume"] = df["volume"].fillna(0)
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
