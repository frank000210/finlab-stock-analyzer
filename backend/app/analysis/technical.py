"""Technical analysis module - TA-Lib wrapper for indicator computation."""

import pandas as pd
import numpy as np
from typing import Optional

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


class TechnicalAnalyzer:
    """Computes technical indicators on OHLCV data."""

    AVAILABLE_INDICATORS = [
        "ma", "ema", "bollinger", "macd", "kd", "rsi",
        "adx", "atr", "obv", "volume"
    ]

    def compute(
        self, df: pd.DataFrame, indicators: list[str], params: Optional[dict] = None
    ) -> pd.DataFrame:
        """Compute requested indicators and merge into dataframe."""
        if df.empty:
            return df

        params = params or {}
        result = df.copy()

        for ind in indicators:
            method = getattr(self, f"_compute_{ind}", None)
            if method:
                result = method(result, params)

        return result

    def get_latest_indicators(
        self, df: pd.DataFrame, indicators: list[str], params: Optional[dict] = None
    ) -> dict:
        """Get the latest value of each indicator."""
        computed = self.compute(df, indicators, params)
        if computed.empty:
            return {}

        last = computed.iloc[-1]
        result = {}

        if "ma" in indicators:
            result["ma"] = {
                "ma5": self._safe_float(last.get("ma5")),
                "ma20": self._safe_float(last.get("ma20")),
                "ma60": self._safe_float(last.get("ma60")),
            }
        if "bollinger" in indicators:
            result["bollinger"] = {
                "upper": self._safe_float(last.get("bb_upper")),
                "middle": self._safe_float(last.get("bb_middle")),
                "lower": self._safe_float(last.get("bb_lower")),
            }
        if "macd" in indicators:
            result["macd"] = {
                "dif": self._safe_float(last.get("macd_dif")),
                "dea": self._safe_float(last.get("macd_dea")),
                "hist": self._safe_float(last.get("macd_hist")),
            }
        if "kd" in indicators:
            result["kd"] = {
                "k": self._safe_float(last.get("k")),
                "d": self._safe_float(last.get("d")),
            }
        if "rsi" in indicators:
            result["rsi"] = {
                "rsi14": self._safe_float(last.get("rsi14")),
            }
        if "adx" in indicators:
            result["adx"] = {
                "adx": self._safe_float(last.get("adx")),
                "plus_di": self._safe_float(last.get("plus_di")),
                "minus_di": self._safe_float(last.get("minus_di")),
            }

        return result

    def _compute_ma(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Simple Moving Averages."""
        periods = params.get("ma_periods", [5, 20, 60])
        for p in periods:
            df[f"ma{p}"] = df["close"].rolling(window=p).mean()
        return df

    def _compute_ema(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Exponential Moving Averages."""
        periods = params.get("ema_periods", [12, 26])
        for p in periods:
            df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()
        return df

    def _compute_bollinger(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Bollinger Bands."""
        period = params.get("bb_period", 20)
        std_dev = params.get("bb_std", 2)

        if HAS_TALIB:
            upper, middle, lower = talib.BBANDS(
                df["close"], timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev
            )
        else:
            middle = df["close"].rolling(window=period).mean()
            std = df["close"].rolling(window=period).std()
            upper = middle + std_dev * std
            lower = middle - std_dev * std

        df["bb_upper"] = upper
        df["bb_middle"] = middle
        df["bb_lower"] = lower
        return df

    def _compute_macd(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """MACD indicator."""
        fast = params.get("macd_fast", 12)
        slow = params.get("macd_slow", 26)
        signal = params.get("macd_signal", 9)

        if HAS_TALIB:
            dif, dea, hist = talib.MACD(
                df["close"], fastperiod=fast, slowperiod=slow, signalperiod=signal
            )
        else:
            ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
            ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
            dif = ema_fast - ema_slow
            dea = dif.ewm(span=signal, adjust=False).mean()
            hist = (dif - dea) * 2

        df["macd_dif"] = dif
        df["macd_dea"] = dea
        df["macd_hist"] = hist
        return df

    def _compute_kd(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Stochastic KD."""
        k_period = params.get("kd_period", 9)
        d_period = params.get("kd_d_period", 3)

        if HAS_TALIB:
            k, d = talib.STOCH(
                df["high"], df["low"], df["close"],
                fastk_period=k_period, slowk_period=d_period, slowd_period=d_period
            )
        else:
            low_min = df["low"].rolling(window=k_period).min()
            high_max = df["high"].rolling(window=k_period).max()
            rsv = (df["close"] - low_min) / (high_max - low_min) * 100
            k = rsv.ewm(com=d_period - 1, adjust=False).mean()
            d = k.ewm(com=d_period - 1, adjust=False).mean()

        df["k"] = k
        df["d"] = d
        return df

    def _compute_rsi(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """RSI indicator."""
        period = params.get("rsi_period", 14)

        if HAS_TALIB:
            df["rsi14"] = talib.RSI(df["close"], timeperiod=period)
        else:
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            df["rsi14"] = 100 - (100 / (1 + rs))

        return df

    def _compute_adx(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """ADX with +DI/-DI."""
        period = params.get("adx_period", 14)

        if HAS_TALIB:
            df["adx"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=period)
            df["plus_di"] = talib.PLUS_DI(df["high"], df["low"], df["close"], timeperiod=period)
            df["minus_di"] = talib.MINUS_DI(df["high"], df["low"], df["close"], timeperiod=period)
        else:
            # CC2：talib 沒裝進 requirements.txt/Dockerfile，這個分支才是實際
            # 部署會跑到的路徑（不是罕見 fallback）——先前這裡整段回傳 NaN，
            # 是死掉的功能。改用 backtest/expr_lang.py::_adx 已經驗證正確的
            # Wilder's DM/ADX 公式（純 pandas，不靠 talib）。
            high, low, close = df["high"], df["low"], df["close"]
            up_move = high.diff()
            down_move = -low.diff()
            plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
            minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
            prev_close = close.shift(1)
            true_range = pd.concat([
                high - low, (high - prev_close).abs(), (low - prev_close).abs(),
            ], axis=1).max(axis=1)
            atr = true_range.ewm(alpha=1 / period, adjust=False).mean()
            plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
            minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
            dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
            df["adx"] = dx.ewm(alpha=1 / period, adjust=False).mean()
            df["plus_di"] = plus_di
            df["minus_di"] = minus_di

        return df

    def _compute_atr(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Average True Range."""
        period = params.get("atr_period", 14)

        if HAS_TALIB:
            df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=period)
        else:
            high_low = df["high"] - df["low"]
            high_close = (df["high"] - df["close"].shift()).abs()
            low_close = (df["low"] - df["close"].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df["atr"] = tr.rolling(window=period).mean()

        return df

    def _compute_obv(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """On-Balance Volume."""
        if HAS_TALIB:
            df["obv"] = talib.OBV(df["close"], df["volume"].astype(float))
        else:
            direction = np.sign(df["close"].diff())
            df["obv"] = (direction * df["volume"]).cumsum()

        return df

    def _compute_volume(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Volume with moving average."""
        df["vol_ma5"] = df["volume"].rolling(window=5).mean()
        df["vol_ma20"] = df["volume"].rolling(window=20).mean()
        return df

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        """Convert to float safely."""
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return round(float(val), 2)
