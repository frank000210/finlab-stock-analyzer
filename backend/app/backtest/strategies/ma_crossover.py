"""MA Crossover Strategy - Buy on golden cross, sell on death cross."""

import pandas as pd
from ..strategy import Strategy


class MACrossoverStrategy(Strategy):

    def setup(self):
        self.name = "MA Crossover"
        self.description = "Buy when fast MA crosses above slow MA; sell on reverse crossover or stop loss."
        self.params.setdefault("fast_ma", 5)
        self.params.setdefault("slow_ma", 20)
        self.params.setdefault("stop_loss", 0.08)
        self.params.setdefault("take_profit", 0.20)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        fast = df["close"].rolling(window=self.params["fast_ma"]).mean()
        slow = df["close"].rolling(window=self.params["slow_ma"]).mean()

        signals = pd.Series(0, index=df.index)
        position = False
        entry_price = 0.0

        for i in range(1, len(df)):
            if not position:
                # Golden cross: fast crosses above slow
                if fast.iloc[i] > slow.iloc[i] and fast.iloc[i - 1] <= slow.iloc[i - 1]:
                    signals.iloc[i] = 1
                    position = True
                    entry_price = df["close"].iloc[i]
            else:
                price = df["close"].iloc[i]
                ret = (price - entry_price) / entry_price

                # Death cross or stop loss or take profit
                if (fast.iloc[i] < slow.iloc[i] and fast.iloc[i - 1] >= slow.iloc[i - 1]):
                    signals.iloc[i] = -1
                    position = False
                elif ret <= -self.params["stop_loss"]:
                    signals.iloc[i] = -1
                    position = False
                elif ret >= self.params["take_profit"]:
                    signals.iloc[i] = -1
                    position = False

        return signals

    @classmethod
    def params_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "fast_ma": {"type": "integer", "default": 5, "minimum": 2, "maximum": 60},
                "slow_ma": {"type": "integer", "default": 20, "minimum": 5, "maximum": 240},
                "stop_loss": {"type": "number", "default": 0.08, "minimum": 0.0, "maximum": 0.5},
                "take_profit": {"type": "number", "default": 0.20, "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["fast_ma", "slow_ma"],
        }
