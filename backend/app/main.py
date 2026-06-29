"""FinLab Stock Analyzer - FastAPI Application."""

import json
import logging
import math
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import (
    admin_router,
    ai_agent_router,
    analysis_router,
    analytics_router,
    auth_router,
    backtest_router,
    cache_router,
    lead_lag_router,
    major_players_router,
    ml_router,
    news_checker_router,
    notifications_router,
    public_data_router,
    risk_router,
    seasonal_router,
    settings_router,
    signal_rules_router,
    social_buzz_router,
    stock_router,
    trade_router,
)
from .config.settings import get_settings

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
        if isinstance(obj, dict):
            return {k: cls._clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [cls._clean(item) for item in obj]
        try:
            import numpy as np

            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                value = float(obj)
                return 0.0 if (math.isnan(value) or math.isinf(value)) else value
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

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_db():
    try:
        from .db.cache import ensure_indexes
        from .db.mongodb import get_mongodb

        await ensure_indexes()
        db = await get_mongodb()
        await db.pageviews.create_index([("page", 1)], unique=True)
        await db.user_logs.create_index([("timestamp", -1)])
        await db.user_logs.create_index("type")
    except Exception as exc:
        logging.warning(f"MongoDB init skipped: {exc}")


@app.on_event("shutdown")
async def shutdown_db():
    try:
        from .db.mongodb import close_mongodb

        await close_mongodb()
    except Exception:
        pass


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
app.include_router(public_data_router)
app.include_router(cache_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version, "routes": len(app.routes)}


frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))
