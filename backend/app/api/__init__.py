from .stock import router as stock_router
from .analysis import router as analysis_router
from .backtest import router as backtest_router
from .ml import router as ml_router
from .notifications import router as notifications_router
from .settings import router as settings_router

__all__ = [
    "stock_router",
    "analysis_router",
    "backtest_router",
    "ml_router",
    "notifications_router",
    "settings_router",
]
