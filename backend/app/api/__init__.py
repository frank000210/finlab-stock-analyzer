from .stock import router as stock_router
from .analysis import router as analysis_router
from .backtest import router as backtest_router
from .ml import router as ml_router
from .notifications import router as notifications_router
from .settings import router as settings_router
from .ai_agent import router as ai_agent_router
from .risk import router as risk_router
from .trade import router as trade_router
from .signal_rules import router as signal_rules_router
from .news_checker import router as news_checker_router

__all__ = [
    "stock_router",
    "analysis_router",
    "backtest_router",
    "ml_router",
    "notifications_router",
    "settings_router",
    "ai_agent_router",
    "risk_router",
    "trade_router",
    "signal_rules_router",
    "news_checker_router",
]
