"""自訂條件策略（BB2）——買進/賣出條件用 expr_lang.py 的運算式語言描述，
不是固定範本。刻意不放進 ALL_STRATEGIES 註冊表：這個策略的合法性（語法對不
對）要在建構當下就檢查，API 層需要能直接捕捉 ExpressionError 給出清楚的
錯誤訊息，而不是像其他固定策略一樣走 strategy_id 查表那條路。
"""

import pandas as pd

from ..expr_lang import eval_condition, parse_condition
from ..strategy import Strategy

CUSTOM_STRATEGY_ID = "custom_expression"


class CustomExpressionStrategy(Strategy):

    def setup(self):
        self.name = "自訂條件"
        self.description = "使用者（或 AI）自訂的買進/賣出條件運算式。"
        # parse_condition 在語法錯誤時丟 ExpressionError，直接往外傳，讓呼叫
        # 端（API handler）決定怎麼轉成給使用者看的錯誤回應。
        self._buy_node = parse_condition(self.params.get("buy_expr", ""))
        self._sell_node = parse_condition(self.params.get("sell_expr", ""))
        stop_loss = self.params.get("stop_loss")
        self._stop_loss = float(stop_loss) if stop_loss else None

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        # 買賣兩條運算式共用同一個快取——常常會用到同一個指標（例如買賣都看
        # RSI(14)），不用算兩次。
        cache: dict = {}
        buy_hits = eval_condition(self._buy_node, df, cache)
        sell_hits = eval_condition(self._sell_node, df, cache)

        position = False
        entry_price = 0.0
        for i in range(len(df)):
            if not position:
                if bool(buy_hits.iloc[i]):
                    signals.iloc[i] = 1
                    position = True
                    entry_price = float(df["close"].iloc[i])
            else:
                price = float(df["close"].iloc[i])
                if bool(sell_hits.iloc[i]):
                    signals.iloc[i] = -1
                    position = False
                elif self._stop_loss and entry_price and (price - entry_price) / entry_price <= -self._stop_loss:
                    signals.iloc[i] = -1
                    position = False
        return signals

    @classmethod
    def params_schema(cls) -> dict:
        return {
            "type": "object",
            "properties": {
                "buy_expr": {"type": "string"},
                "sell_expr": {"type": "string"},
                "stop_loss": {"type": "number", "default": 0.08, "minimum": 0.0, "maximum": 0.5},
            },
            "required": ["buy_expr", "sell_expr"],
        }
