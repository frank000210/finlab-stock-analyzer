"""MACD Trend Strategy - Trade based on MACD histogram."""

import pandas as pd
from ..strategy import Strategy


class MACDStrategy(Strategy):

    def setup(self):
        self.name = "MACD Trend"
        self.description = "Buy when MACD histogram turns positive; sell when it turns negative or stop loss."
        self.params.setdefault("macd_fast", 12)
        self.params.setdefault("macd_slow", 26)
        self.params.setdefault("macd_signal", 9)
        self.params.setdefault("stop_loss", 0.08)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "macd_hist" not in df.columns:
            return signals

        position = False
        entry_price = 0.0

        for i in range(1, len(df)):
            hist = df["macd_hist"].iloc[i]
            prev_hist = df["macd_hist"].iloc[i - 1]

            if not position:
                # MACD histogram crosses above zero
                if hist > 0 and prev_hist <= 0:
                    signals.iloc[i] = 1
                    position = True
                    entry_price = df["close"].iloc[i]
            else:
                price = df["close"].iloc[i]
                ret = (price - entry_price) / entry_price

                if hist < 0 and prev_hist >= 0:
                    signals.iloc[i] = -1
                    position = False
                elif ret <= -self.params["stop_loss"]:
                    signals.iloc[i] = -1
                    position = False

        return signals

    @classmethod
    def params_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "macd_fast": {"type": "integer", "default": 12, "minimum": 5, "maximum": 50},
                "macd_slow": {"type": "integer", "default": 26, "minimum": 10, "maximum": 100},
                "macd_signal": {"type": "integer", "default": 9, "minimum": 3, "maximum": 30},
                "stop_loss": {"type": "number", "default": 0.08, "minimum": 0.0, "maximum": 0.5},
            },
            "required": ["macd_fast", "macd_slow", "macd_signal"],
        }
