# Deployment, Operations & Testing

This page covers how the application is deployed, the operational tooling, and how testing is organized.

## Deployment architecture

The project ships as a **single Docker image** that contains both the FastAPI backend and the built Vue SPA.

- FastAPI serves `/api/*` routes.
- FastAPI serves static files from `frontend/dist`.
- Any unmatched path returns `index.html` so Vue Router handles client-side routing.
- `/api/*` 404s are preserved (not swallowed by the SPA fallback) to surface real backend errors.

Target platform: **Zeabur**.

| Config | Value (from handover) |
|--------|----------------------|
| Project ID | `6a3f6ff522d1fdaf7eb04d04` |
| Service ID | `6a3f700322d1fdaf7eb04d06` |
| Public URL | `https://finlab-app.zeabur.app` |
| Branch | `master` |

## Build process

`Dockerfile`:

1. Frontend build stage (`node:20-alpine`)
   - Installs npm dependencies.
   - Runs `npm run build` to produce `frontend/dist`.
2. Python runtime stage (`python:3.11-slim`)
   - Installs Python requirements.
   - Installs `TA-Lib==0.6.8` as a prebuilt wheel (no source compilation).
   - Copies backend code and the built frontend.
   - Runs uvicorn on `0.0.0.0:8080`.

The Dockerfile documents a historical lesson: earlier versions compiled TA-Lib from source, but that broke repeatedly on newer gcc; the current approach relies on upstream manylinux wheels.

## Continuous deployment

`.github/workflows/deploy.yml` triggers on every push to `master`:

```bash
npx zeabur deploy --project-id ... --service-id ... -i=false
```

Requires `ZEABUR_TOKEN` in GitHub secrets.

## Local development environment

Use the scripts in `scripts/` or the commands below.

### PowerShell one-liner

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

This typically starts MongoDB and loads `FINMIND_TOKEN` from Windows environment variables. Inspect the script for exact behavior.

### Manual backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Copy .env.example -> .env and fill in secrets
uvicorn app.main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/api/health`
Swagger: `http://localhost:8000/api/docs`

### Manual frontend

```powershell
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `localhost:8000` in development.

### Manual Docker

```bash
docker build -t finlab-stock-analyzer .
docker run -p 8000:8080 --env-file .env finlab-stock-analyzer
```

Note: the container listens on `8080`; map it to host `8000` because the frontend dev server assumes `localhost:8000` for API proxy.

## Required environment variables

Copy `.env.example` to `.env` and configure at minimum:

- `FINMIND_TOKEN` — primary market data
- `MONGODB_URI` — cache and logs (optional for dev; degrades gracefully)
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Telegram alerts
- `LINE_NOTIFY_TOKEN` — LINE alerts (legacy)
- `GOOGLE_CLIENT_ID` — Google sign-in
- `ADMIN_SECRET` — JWT signing (random per-process if unset; set in production!)

See `backend/app/config/settings.py` for the full schema and defaults.

## Testing

### End-to-end tests

The project uses **Playwright** for E2E testing in `e2e/`.

- Config: `e2e/playwright.config.js`
- Tests: `e2e/tests/*.spec.js`
- Default base URL: `http://localhost:8000`
- Single worker, non-parallel, 120s timeout.

Run:

```bash
cd e2e
npm install
npx playwright install chromium
npm test
```

Run against dev server:

```bash
BASE_URL=http://localhost:5173 npm test
```

Generate new tests:

```bash
npm run codegen
```

### E2E test categories

| Spec | Focus |
|------|-------|
| `smoke.spec.js` | Core pages load and render real data |
| `analysis-chart.spec.js` | Technical chart rendering |
| `backtest-costs.spec.js` / `backtest-mfe-mae.spec.js` / `backtest-overfit.spec.js` | Backtest correctness |
| `command.spec.js` / `loss-limit-breaker.spec.js` | Command dashboard risk rules |
| `daily-brief.spec.js` / `daily-brief-page.spec.js` | Post-close brief |
| `journal*.spec.js` | Trade journal coaching features |
| `monte-carlo*.spec.js` | Monte Carlo simulation |
| `portfolio-heat.spec.js` / `portfolio-stress-test.spec.js` / `risk-sizing*.spec.js` | Risk workflows |
| `price-alerts.spec.js` | Telegram price alerts |
| `pwa.spec.js` | PWA installability / offline shell |
| `sidebar.spec.js` / `mobile-nav.spec.js` / `quick-switcher.spec.js` | Navigation UX |
| `signals.spec.js` / `us-stocks.spec.js` / `stock-calendar.spec.js` | Signals and US stock support |

### Backend unit tests

`backend/tests/` is currently empty. Backend correctness is validated primarily through E2E tests and runtime smoke checks.

### Local validation checklist

Before committing, the project convention requires:

1. Frontend build passes: `cd frontend && npm run build`
2. Backend imports cleanly: `cd backend && python -c "from app.main import app; print('OK')"`
3. E2E smoke tests green (when data sources are available).

## Automated OpenWiki updates

`.github/workflows/openwiki-update.yml` runs daily at 08:00 UTC:

1. Checks out the repo.
2. Installs the global `openwiki` CLI.
3. Runs `openwiki code --update --print`.
4. Creates a pull request from `openwiki/update` with changes to:
   - `openwiki/`
   - `AGENTS.md`
   - `CLAUDE.md`
   - `.github/workflows/openwiki-update.yml`

It uses `OPENAI_COMPATIBLE_API_KEY` / `OPENAI_COMPATIBLE_BASE_URL` (OpenCode Go plan, model `kimi-k2.7-code`) and optionally traces to LangSmith.

## Operational notes

- **MongoDB is optional**: the backend degrades gracefully if MongoDB is unavailable, skipping cache/logs.
- **Scheduler is optional**: set `AUTO_INGEST_ENABLED=false` to disable post-close ingestion.
- **Data staleness**: many pages show `DataLineage` badges with source and as-of timestamps.
- **PWA**: the service worker caches hashed assets but never caches `/api/*`, so market data is always fresh when online; navigations fall back to the cached shell when offline.

## Source map

- `Dockerfile` — build definition.
- `.github/workflows/deploy.yml` — Zeabur CD.
- `.github/workflows/openwiki-update.yml` — documentation refresh.
- `backend/app/config/settings.py` — environment configuration.
- `backend/app/scheduler.py` — post-close auto-ingest.
- `frontend/public/sw.js` — PWA service worker.
- `frontend/public/manifest.webmanifest` — PWA manifest.
- `e2e/playwright.config.js` — E2E config.
- `e2e/tests/*.spec.js` — E2E tests.
