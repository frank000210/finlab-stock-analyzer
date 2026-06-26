from .ma_crossover import MACrossoverStrategy
from .macd_strategy import MACDStrategy
from .bollinger_strategy import BollingerStrategy
from .rsi_strategy import RSIReversionStrategy

ALL_STRATEGIES = {
    "ma_crossover": MACrossoverStrategy,
    "macd_trend": MACDStrategy,
    "bollinger_breakout": BollingerStrategy,
    "rsi_reversion": RSIReversionStrategy,
}

__all__ = ["ALL_STRATEGIES", "MACrossoverStrategy", "MACDStrategy", "BollingerStrategy", "RSIReversionStrategy"]
