import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .api import auth, notebooks, imports, ask

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NN8: sentence-transformers is lazy-loaded on first use; without this,
    # the first /api/ask or /api/import call after a cold start pays the
    # multi-second model-load cost on top of the user's actual request.
    try:
        from knowledge_base.semantic_search import _embed

        _embed("warmup")
    except Exception:
        logger.warning("Semantic model warm-up failed; will lazy-load on first use instead.")
    yield


app = FastAPI(title="Knowledge Base Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    # NN5: unauthenticated probe target, independent of whether the SPA's
    # index.html happens to be reachable -- lets Zeabur/monitoring check
    # the API process specifically.
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(notebooks.router)
app.include_router(imports.router)
app.include_router(ask.router)

frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Vue Router uses HTML5 history mode, so every client-side route
        # (/login, /import, /ask, ...) must resolve to index.html and let
        # the router take over -- StaticFiles(html=True) alone only does
        # this for "/", not arbitrary paths.
        return FileResponse(frontend_dist / "index.html")
