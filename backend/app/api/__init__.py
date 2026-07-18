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
from .seasonal import router as seasonal_router
from .lead_lag import router as lead_lag_router
from .major_players import router as major_players_router
from .chip import router as chip_router
from .social_buzz import router as social_buzz_router
from .public_data import router as public_data_router
from .cache import router as cache_router
from .analytics import router as analytics_router
from .auth import router as auth_router
from .admin import router as admin_router
from .graph import router as graph_router
from .rotation import router as rotation_router
from .peers import router as peers_router

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
    "seasonal_router",
    "lead_lag_router",
    "major_players_router",
    "chip_router",
    "social_buzz_router",
    "public_data_router",
    "cache_router",
    "analytics_router",
    "auth_router",
    "admin_router",
    "graph_router",
    "rotation_router",
    "peers_router",
]
