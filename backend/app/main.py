"""FinLab Stock Analyzer - FastAPI Application."""

import math
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path

from .config.settings import get_settings
from .api import (
    stock_router,
    analysis_router,
    backtest_router,
    ml_router,
    notifications_router,
    settings_router,
    ai_agent_router,
    risk_router,
    trade_router,
    signal_rules_router,
    news_checker_router,
    seasonal_router,
    lead_lag_router,
    major_players_router,
    social_buzz_router,
)

settings = get_settings()


class SafeJSONResponse(JSONResponse):
    """JSON response that handles NaN/Infinity and numpy types."""

    def render(self, content) -> bytes:
        cleaned = self._clean(content)
        return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")

    @classmethod
    def _clean(cls, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return 0.0
            return obj
        elif isinstance(obj, dict):
            return {k: cls._clean(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [cls._clean(item) for item in obj]
        # Handle numpy types
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                v = float(obj)
                return 0.0 if (math.isnan(v) or math.isinf(v)) else v
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return [cls._clean(x) for x in obj.tolist()]
        except (ImportError, TypeError):
            pass
        return obj


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    default_response_class=SafeJSONResponse,
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(stock_router)
app.include_router(analysis_router)
app.include_router(backtest_router)
app.include_router(ml_router)
app.include_router(notifications_router)
app.include_router(settings_router)
app.include_router(ai_agent_router)
app.include_router(risk_router)
app.include_router(trade_router)
app.include_router(signal_rules_router)
app.include_router(news_checker_router)
app.include_router(seasonal_router)
app.include_router(lead_lag_router)
app.include_router(major_players_router)
app.include_router(social_buzz_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version}


# Serve frontend static files in production (must be AFTER API routes)
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.responses import FileResponse

    # SPA catch-all: serve index.html for any non-API, non-static route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If the path is a real file in dist, serve it
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise return index.html for Vue Router
        return FileResponse(str(frontend_dist / "index.html"))
