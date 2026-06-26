"""Base Strategy class - all strategies inherit from this."""

from abc import ABC, abstractmethod
from typing import Any
import pandas as pd


class Strategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(self, params: dict[str, Any] = None):
        self.params = params or {}
        self.name: str = "Base Strategy"
        self.description: str = ""
        self.setup()

    @abstractmethod
    def setup(self):
        """Initialize strategy name, description, and default params."""
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals.
        
        Args:
            df: DataFrame with OHLCV + indicators
            
        Returns:
            Series with values:
                1 = buy signal
                0 = hold / no position
                -1 = sell signal
        """
        pass

    @classmethod
    def params_schema(cls) -> dict:
        """Return JSON Schema for strategy parameters."""
        return {"type": "object", "properties": {}}
