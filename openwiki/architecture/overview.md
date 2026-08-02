# Architecture Overview

## System layout

FinLab Stock Analyzer is a **single-container, same-origin** web application: a FastAPI backend serves both the JSON API (`/api/*`) and the built Vue SPA (`frontend/dist`), so there is no CORS complexity in production and only one deployable artifact.

```
Browser
  │
  ├─ /api/v1/*      → FastAPI routers
  └─ /{any_path}    → StaticFiles / SPA fallback → index.html

Server (Docker @ Zeabur :8080)
  ├── FastAPI + uvicorn
  ├── StaticFiles (frontend/dist)
  └── MongoDB cache/log (optional, graceful fallback)

Data sources
  ├── FinMind API (primary)
  ├── yfinance (US/fallback)
  └── TWSE / TDCC public data (free sources)
```

Key design decisions (from `docs/03-技術架構.md` and source):

- **One image** — `Dockerfile` builds the frontend first, copies `frontend/dist` into the Python image, then runs `uvicorn app.main:app` on `PORT=8080`.
- **Same-origin API** — `frontend/.env.production` uses `API_BASE=''`; local dev uses the Vite proxy to `localhost:8000`.
- **SPA fallback** — `backend/app/main.py` registers a catch-all `/{full_path:path}` that returns `index.html` for unknown paths, but **explicitly rejects `/api/*` mismatches** with 404 so API failures are not masked by HTML.

## Backend architecture

### App assembly (`backend/app/main.py`)

- Creates the FastAPI app with `lifespan` (replaces deprecated `on_event`).
- Registers **20+ routers** imported from `backend/app/api/__init__.py`.
- Attaches `CORSMiddleware` with origins from `CORS_ORIGINS`.
- Uses a custom `SafeJSONResponse` as `default_response_class` to coerce NaN/Inf and numpy scalars to plain JSON.
- On startup:
  - Ensures MongoDB indexes (`pageviews`, `user_logs`).
  - Starts the post-close auto-ingest scheduler (`backend/app/scheduler.py`).

### Routing convention

Each feature owns one file in `backend/app/api/` exporting an `APIRouter` with a `prefix="/api/v1/<feature>"`. Routers are imported and `include_router`-ed in `main.py`.

```python
# backend/app/api/__init__.py
from .stock import router as stock_router
from .analysis import router as analysis_router
...
```

The `api/` layer is intentionally thin: validation + assembly only. Heavy computation lives in `analysis/`, `backtest/`, `ml/`, `risk/`, `trade/`, `notify/`, `ai_agent/`, `signal_rules/`.

### Service layers

| Directory | Responsibility | Example |
|-----------|----------------|---------|
| `backend/app/api/` | HTTP routers, request/response | `analysis.py`, `risk.py`, `backtest.py` |
| `backend/app/analysis/` | Pure computation, no HTTP | `technical.py`, `chip_distribution.py`, `sector_rotation.py`, `watch_graph.py` |
| `backend/app/crawler/` | Data fetching adapters | `finmind_client.py`, `stock_price.py`, `institutional.py`, `fundamental.py`, `twse_public.py` |
| `backend/app/backtest/` | Strategy engine + built-in strategies | `engine.py` |
| `backend/app/ml/` | Random Forest predictor | `predictor.py` |
| `backend/app/risk/` | Risk manager | `manager.py` |
| `backend/app/notify/` | LINE/Telegram push | `line.py`, `telegram.py` |
| `backend/app/db/` | Cache + MongoDB | `cache.py`, `cached.py`, `mongodb.py`, `memcache.py` |

## Frontend architecture

### App bootstrap (`frontend/src/main.js`)

- Creates Vue 3 app with Pinia + Router.
- Applies saved theme before mount to avoid flash.
- Registers a global `v-reveal` directive for scroll/enter animations.
- Registers a global `app.config.errorHandler` that surfaces component errors as a `finlab:app-error` custom event so `App.vue` can show a toast instead of silently blanking the subtree.
- Registers the service worker only in production (`import.meta.env.PROD`) to avoid dev/HMR conflicts.

### Layout (`frontend/src/App.vue`)

- Always renders `AppSidebar` + `main-content` for the router view.
- First-visit onboarding banner on `/`.
- `PageCounter` (global usage tracking) and `QuickSwitcher` (Ctrl/Cmd+K global navigation).
- Global error toast stack.

### Routing (`frontend/src/router.js`)

- Uses `createWebHistory`.
- All views are lazy-loaded with `() => import(...)` so each page becomes its own chunk.
- Routes are grouped by feature:
  - Top-level pages: `/`, `/overview`, `/decision`, `/graph`, `/rotation`, `/guide`, `/settings`, `/admin`
  - Symbol-scoped pages: `/stocks/:symbol`, `/stocks/:symbol/backtest`, `/stocks/:symbol/seasonal`, etc.
  - Newer risk/trade pages: `/risk-sizing`, `/portfolio-heat`, `/journal`, `/monte-carlo`, `/price-alerts`, `/signals`, `/daily-brief`, `/command`

### Design system

- CSS variables defined in `frontend/src/assets/main.css` (colors, spacing, typography, up/down colors).
- **涨/跌 colors**: `--color-up` / `--color-down` (do not hard-code red/green).
- **Tabular numbers**: `font-variant-numeric: tabular-nums` for financial figures.
- **Charts**: candle/line charts use `lightweight-charts`; custom visualizations (treemap, box plot, chord, sankey, horizon, calendar, histogram/KDE) use D3.
- **Motion**: `v-reveal` directive (content is visible by default; animation is enhancement only). The directive was fixed to clear `will-change` after animation so fullscreen overlays are not trapped in a stale containing block.
- **Theme**: runtime theme overrides via `frontend/src/composables/useTheme.js`.

## Data flow

1. Frontend calls `apiGet(path)` (or `fetch`) to `/api/v1/<feature>/...`.
2. Backend router validates query/path params.
3. Router calls `analysis` / `crawler` / `ml` / `risk` layer, usually with `asyncio.gather(..., return_exceptions=True)` for parallel data sources.
4. Heavy results are cached in MongoDB (versioned cache keys, e.g. `chip_analysis:v5:<symbol>`).
5. `SafeJSONResponse` cleans the payload before serialization.
6. Frontend receives `{"success": true, "data": ...}` and must verify shape before use (per `docs/04-開發指引.md`).

## Key shared abstractions

| Abstraction | File | Purpose |
|-------------|------|---------|
| `SafeJSONResponse` | `backend/app/main.py` | Convert NaN/Inf/numpy to plain JSON |
| `get_settings()` | `backend/app/config/settings.py` | Cached pydantic-settings singleton |
| `cached` decorator / `cache.py` | `backend/app/db/cached.py` | MongoDB-backed versioned cache |
| `apiGet()` | `frontend/src/views/*.vue` (common helper) | Fetch + shape validation |
| `useStockStore()` | `frontend/src/stores/stock.js` | Current symbol/name (read-only) |
| `v-reveal` | `frontend/src/directives/reveal.js` | Scroll enter animation with failsafe |
| `PageFocusBanner` | `frontend/src/components/PageFocusBanner.vue` | Page observation-focus banner |

## Source map

- `backend/app/main.py` — app assembly, health check, SPA fallback.
- `backend/app/api/__init__.py` — router exports.
- `backend/app/config/settings.py` — settings + env vars.
- `frontend/src/main.js` — Vue app bootstrap.
- `frontend/src/App.vue` — layout, error toast, onboarding, page counter, quick switcher.
- `frontend/src/router.js` — route table.
- `frontend/src/assets/main.css` — design tokens.
- `Dockerfile` — single-image build.
