# FinLab Stock Analyzer OpenWiki

This is the OpenWiki knowledge base for **finlab-stock-analyzer**, a Taiwan-stock AI analysis web application. The repo is documented by [OpenWiki](https://github.com/...) on a scheduled GitHub Actions workflow; start here and follow the section links below.

## What this project is

A single-page web app for deep analysis of individual Taiwanese stocks (recently extended to include US indices/sector leaders). It combines:

- Technical analysis (K-line, MA, Bollinger, MACD, KD, RSI, volume profile, candle calendar)
- Fundamental analysis (monthly revenue, EPS, margins, PE/PB band)
- Chip analysis (institutional flows, margin, major-player cost, distribution health)
- Market rotation & lead-lag (RRG, sector heatmap, chord/horizon charts, correlation graph)
- AI signals & decision dashboard (Random Forest BUY/SELL/HOLD, setup scores)
- Strategy backtest (MA crossover, MACD, Bollinger, RSI, MFE/MAE, walk-forward IS/OOS)
- Risk & trade discipline (position sizing, Kelly, Monte Carlo, portfolio heat, daily loss-limits, trade journal, paper trading)
- Notifications (LINE, Telegram push alerts)

## Repository entry points

| Layer | Key files | Purpose |
|-------|-----------|---------|
| Frontend | `frontend/src/main.js`, `frontend/src/App.vue`, `frontend/src/router.js` | Vue 3 app bootstrap, layout, routing |
| Backend | `backend/app/main.py` | FastAPI app assembly, routers, SPA fallback, health |
| Config | `backend/app/config/settings.py` | Pydantic settings; all secrets via env |
| Schedules | `backend/app/scheduler.py` | Post-close auto-ingest of sector/watchlist data |
| Docs | `README.md`, `USER_GUIDE.md`, `docs/03-技術架構.md`, `docs/04-開發指引.md` | Human-readable product/dev docs |

## Quick start

```bash
# Backend
cd backend
pip install -r requirements.txt
# Copy .env.example -> .env and fill FINMIND_TOKEN
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173

# Docker (single image, deploys to Zeabur)
docker build -t finlab-stock-analyzer .
docker run -p 8000:8080 --env-file .env finlab-stock-analyzer
```

Live API docs: `http://localhost:8000/api/docs` (Swagger UI).

## Wiki sections

- **[Architecture](architecture/overview.md)** — system layout, single-container design, routing, data flow, key abstractions like `SafeJSONResponse`.
- **[Architecture](architecture/overview.md)** — system layout, single-container design, routing, data flow, key abstractions like `SafeJSONResponse`.
- **[Frontend](domain/frontend.md)** — views, router, design system, shared components, state management, charts.
- **[Backend](domain/backend.md)** — API layer, analysis modules, crawlers, backtest engine, ML, risk/trade/notify.
- **[Workflows](workflows/development.md)** — development SOP, conventions, PageFocusBanner rule, commit style, quality gates.
- **[Operations](operations/deployment.md)** — Docker, Zeabur deployment, local scripts, scheduled auto-ingest, OpenWiki workflow, E2E testing.

## Important conventions for future agents

1. **Read before writing**: existing docs (`docs/03-技術架構.md`, `docs/04-開發指引.md`, `docs/06-頁面觀測重點與改動清單.md`) are the source of truth for architecture and page design.
2. **One page, one observation focus**: every non-home page must state its single observation focus in a `PageFocusBanner` at the top of `frontend/src/views/XxxView.vue`.
3. **Backend API response shape**: return `{"success": true, "data": ...}` and let `SafeJSONResponse` clean NaN/numpy values.
4. **Secrets**: only via environment variables loaded by `backend/app/config/settings.py`; never hard-code tokens.
5. **One verifiable increment per commit**: use Conventional Commits (`feat/fix/docs/chore`), build/import must pass before committing.
6. **Do not edit generated OpenWiki pages by hand** unless asked; update source docs or code and let the workflow regenerate.

## Backlog

| Area | Source anchor | Why deferred |
|------|---------------|--------------|
| Per-view API/data-flow mapping | `frontend/src/views/*.vue`, `backend/app/api/*.py` | Too large for initial pass; can be expanded incrementally as views change |
| Backtest engine internals | `backend/app/backtest/` | Functional overview covered; detailed strategy implementations need a dedicated page only if the engine grows |
