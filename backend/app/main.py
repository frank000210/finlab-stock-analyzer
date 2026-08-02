"""FinLab Stock Analyzer - FastAPI Application."""

import json
import logging
import math
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import (
    admin_router,
    kb_router,
    ai_summary_router,
    ai_agent_router,
    journal_router,
    screener_router,
    feedback_router,
    analysis_router,
    analytics_router,
    auth_router,
    backtest_router,
    cache_router,
    graph_router,
    rotation_router,
    lead_lag_router,
    major_players_router,
    chip_router,
    market_router,
    news_checker_router,
    notifications_router,
    peers_router,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動時初始化 MongoDB 索引,關閉時釋放連線(取代已棄用的 on_event)。"""
    try:
        from .db.cache import ensure_indexes
        from .db.mongodb import get_mongodb

        await ensure_indexes()
        db = await get_mongodb()
        await db.pageviews.create_index([("page", 1)], unique=True)
        await db.user_logs.create_index([("timestamp", -1)])
        await db.user_logs.create_index("type")
        # JJ3：user_logs 先前只有排序/篩選用的一般索引，沒有 TTL——
        # POST /pageview、/user-identify 兩支公開端點沒有任何頻率限制，
        # 這個 collection 會無上限成長。90 天足夠 admin 後台的訪客統計/
        # 稽核用途，用另一支獨立的升冪 TTL 索引（跟既有的降冪排序索引
        # 分開，不衝突）讓舊資料自動過期。
        await db.user_logs.create_index([("timestamp", 1)], expireAfterSeconds=7776000)
    except Exception as exc:
        logging.warning(f"MongoDB init skipped: {exc}")

    # 每日收盤後自動 re-ingest 關聯圖/類股輪動資料
    try:
        from .scheduler import start_scheduler

        start_scheduler()
    except Exception as exc:
        logging.warning(f"auto-ingest scheduler not started: {exc}")

    # S1：載入使用者自訂訊號規則（原本只存在記憶體，重啟就消失）
    try:
        from .signal_rules.engine import rule_engine

        await rule_engine.load_rules()
    except Exception as exc:
        logging.warning(f"signal rules load skipped: {exc}")

    yield

    try:
        from .scheduler import stop_scheduler

        stop_scheduler()
    except Exception:
        pass

    try:
        from .db.mongodb import close_mongodb

        await close_mongodb()
    except Exception:
        pass

    try:
        from .crawler.finmind_client import close_finmind_client

        await close_finmind_client()
    except Exception:
        pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    default_response_class=SafeJSONResponse,
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stock_router)
app.include_router(analysis_router)
app.include_router(backtest_router)
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
app.include_router(chip_router)
app.include_router(social_buzz_router)
app.include_router(public_data_router)
app.include_router(cache_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(graph_router)
app.include_router(rotation_router)
app.include_router(peers_router)
app.include_router(market_router)
app.include_router(ai_summary_router)
app.include_router(journal_router)
app.include_router(screener_router)
app.include_router(feedback_router)
app.include_router(kb_router)


BUILD_INFO_PATH = Path(__file__).parent / "build_info.json"


def _read_build_info_once() -> dict:
    """AA1: Read once at import time; no per-request I/O."""
    try:
        return json.loads(BUILD_INFO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _git_commit_hash_once() -> str | None:
    """AA1: Run git at import time so health_check() is non-blocking."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
            cwd=Path(__file__).parent,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


_BUILD_INFO = _read_build_info_once()
_COMMIT_HASH = _BUILD_INFO.get("commit") or _git_commit_hash_once()


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": settings.app_version,
        "routes": len(app.routes),
        "build_time": _BUILD_INFO.get("build_time"),
        "commit": _COMMIT_HASH,
    }


@app.get("/api/ready")
async def readiness_check():
    """S4：/api/health 只確認「行程活著」，不管 MongoDB 連得上或 FinMind
    token 有沒有設定都回 200——這支額外探測關鍵依賴，讓監控/維運能分辨
    「行程活著但功能壞掉」跟「真的完全健康」。依賴壞掉時回 503，方便給
    load balancer / uptime 監控用來判斷是否該把流量導開。
    """
    checks: dict[str, str] = {}
    try:
        from .db.mongodb import get_mongodb

        db = await get_mongodb()
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:
        checks["mongodb"] = f"error: {exc}"

    checks["finmind_token"] = "ok" if settings.finmind_token else "missing"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )


frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Never let the SPA fallback swallow API routes: an unmatched
        # /api/* path means a real 404 (unknown endpoint / typo), not a
        # client-side route. Without this, a bad API path silently returns
        # index.html with HTTP 200, which masks backend/deploy failures.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"Not found: /{full_path}")
        # II1：full_path 是 URL 路徑直接轉成的字串，Starlette 的 path
        # convertor 不會處理 `..`。沒有這層防護的話 frontend_dist/full_path
        # 可以逃出 dist 目錄，讀到任意伺服器檔案（已用 GET /../../backend/
        # app/config/settings.py 實測成功讀出源碼）。resolve() 後確認仍在
        # frontend_dist 底下才放行，其餘一律當成 SPA 路由回 index.html。
        file_path = (frontend_dist / full_path).resolve()
        if file_path.is_relative_to(frontend_dist.resolve()) and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))
