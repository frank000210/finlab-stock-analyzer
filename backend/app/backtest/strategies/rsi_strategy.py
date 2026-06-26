"""RSI Reversion Strategy - Buy oversold, sell overbought."""

import pandas as pd
from ..strategy import Strategy


class RSIReversionStrategy(Strategy):

    def setup(self):
        self.name = "RSI Reversion"
        self.description = "Buy when RSI crosses above oversold level; sell when RSI crosses below overbought."
        self.params.setdefault("rsi_period", 14)
        self.params.setdefault("oversold", 30)
        self.params.setdefault("overbought", 70)
        self.params.setdefault("stop_loss", 0.08)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "rsi14" not in df.columns:
            return signals

        position = False
        entry_price = 0.0

        for i in range(1, len(df)):
            rsi = df["rsi14"].iloc[i]
            prev_rsi = df["rsi14"].iloc[i - 1]

            if pd.isna(rsi) or pd.isna(prev_rsi):
                continue

            if not position:
                # RSI crosses above oversold
                if rsi > self.params["oversold"] and prev_rsi <= self.params["oversold"]:
                    signals.iloc[i] = 1
                    position = True
                    entry_price = df["close"].iloc[i]
            else:
                price = df["close"].iloc[i]
                ret = (price - entry_price) / entry_price

                # RSI crosses below overbought (from above)
                if rsi < self.params["overbought"] and prev_rsi >= self.params["overbought"]:
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
                "rsi_period": {"type": "integer", "default": 14, "minimum": 5, "maximum": 30},
                "oversold": {"type": "integer", "default": 30, "minimum": 10, "maximum": 40},
                "overbought": {"type": "integer", "default": 70, "minimum": 60, "maximum": 90},
                "stop_loss": {"type": "number", "default": 0.08, "minimum": 0.0, "maximum": 0.5},
            },
            "required": ["oversold", "overbought"],
        }
