from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .api import auth, notebooks, imports, ask

settings = get_settings()

app = FastAPI(title="Knowledge Base Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(notebooks.router)
app.include_router(imports.router)
app.include_router(ask.router)

frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="spa")
