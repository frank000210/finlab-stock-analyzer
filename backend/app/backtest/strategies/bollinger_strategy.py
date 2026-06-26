"""Bollinger Band Breakout Strategy."""

import pandas as pd
from ..strategy import Strategy


class BollingerStrategy(Strategy):

    def setup(self):
        self.name = "Bollinger Breakout"
        self.description = "Buy when price breaks above upper band with volume; sell on middle band or stop loss."
        self.params.setdefault("bb_period", 20)
        self.params.setdefault("bb_std", 2)
        self.params.setdefault("stop_loss", 0.08)
        self.params.setdefault("volume_ratio", 1.5)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "bb_upper" not in df.columns or "bb_middle" not in df.columns:
            return signals

        position = False
        entry_price = 0.0

        for i in range(1, len(df)):
            if not position:
                # Price breaks above upper band with volume surge
                vol_ma = df["volume"].iloc[max(0, i-20):i].mean() if i > 0 else 0
                vol_ok = df["volume"].iloc[i] > vol_ma * self.params["volume_ratio"] if vol_ma > 0 else False

                if df["close"].iloc[i] > df["bb_upper"].iloc[i] and vol_ok:
                    signals.iloc[i] = 1
                    position = True
                    entry_price = df["close"].iloc[i]
            else:
                price = df["close"].iloc[i]
                ret = (price - entry_price) / entry_price

                # Sell when price falls below middle band
                if price < df["bb_middle"].iloc[i]:
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
                "bb_period": {"type": "integer", "default": 20, "minimum": 10, "maximum": 50},
                "bb_std": {"type": "number", "default": 2, "minimum": 1.0, "maximum": 3.0},
                "stop_loss": {"type": "number", "default": 0.08, "minimum": 0.0, "maximum": 0.5},
                "volume_ratio": {"type": "number", "default": 1.5, "minimum": 1.0, "maximum": 5.0},
            },
            "required": ["bb_period", "bb_std"],
        }
