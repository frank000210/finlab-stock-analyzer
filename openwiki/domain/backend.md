# Backend Domain & Services

The backend is a FastAPI application (`backend/app/main.py`) structured into thin routers, computational analysis modules, data crawlers, and support services. This page explains the major domains and their important source files.

## API routers

All routes live under `backend/app/api/` and share the unified response shape `{"success": true, "data": ...}`.

| Router | Prefix | Main concern | Key file |
|--------|--------|--------------|----------|
| `stock_router` | `/api/v1/stocks` | Price lookup, search, US symbol normalization | `backend/app/api/stock.py` |
| `analysis_router` | `/api/v1/analysis` | Technical / fundamental / calendar data | `backend/app/api/analysis.py` |
| `backtest_router` | `/api/v1/backtest` | Strategy backtesting + overfit guard | `backend/app/api/backtest.py` |
| `ml_router` | `/api/v1/ml` | Random Forest predictions | `backend/app/api/ml.py` |
| `risk_router` | `/api/v1/risk` | Risk sizing, portfolio heat, price alerts, daily brief, market regime | `backend/app/api/risk.py` |
| `trade_router` | `/api/v1/trade` | Trade approval/order flow | `backend/app/api/trade.py` |
| `signal_rules_router` | `/api/v1/signal-rules` | Rule-based signal management | `backend/app/api/signal_rules.py` |
| `news_checker_router` | `/api/v1/news` | News/announcement checking | `backend/app/api/news_checker.py` |
| `ai_agent_router` | `/api/v1/ai-agent` | AI signal generation | `backend/app/api/ai_agent.py` |
| `notifications_router` | `/api/v1/notifications` | LINE/Telegram push | `backend/app/api/notifications.py` |
| `settings_router` | `/api/v1/settings` | Frontend settings / Google Client ID | `backend/app/api/settings.py` |
| `auth_router` | `/api/v1/auth` | Google OAuth admin login | `backend/app/api/auth.py` |
| `admin_router` | `/api/v1/admin` | Admin dashboards / analytics | `backend/app/api/admin.py` |
| `analytics_router` | `/api/v1/analytics` | Pageviews / user logs | `backend/app/api/analytics.py` |
| `graph_router` | `/api/v1/graph` | Watch-graph network + correlation | `backend/app/api/graph.py` |
| `rotation_router` | `/api/v1/rotation` | Sector rotation / RRG / heatmap | `backend/app/api/rotation.py` |
| `chip_router` | `/api/v1/chip` | Chip analysis + score | `backend/app/api/chip.py` |
| `seasonal_router` | `/api/v1/seasonal` | Seasonal stats | `backend/app/api/seasonal.py` |
| `lead_lag_router` | `/api/v1/lead-lag` | Lead-lag relationships | `backend/app/api/lead_lag.py` |
| `major_players_router` | `/api/v1/major-players` | Major player capital flow | `backend/app/api/major_players.py` |
| `social_buzz_router` | `/api/v1/social-buzz` | News/social sentiment | `backend/app/api/social_buzz.py` |
| `public_data_router` | `/api/v1/public-data` | Public data pass-through | `backend/app/api/public_data.py` |
| `cache_router` | `/api/v1/cache` | Cache introspection | `backend/app/api/cache.py` |

## Analysis modules

`backend/app/analysis/` contains the computational core. They should be pure functions that can be tested without HTTP.

| Module | Concern |
|--------|---------|
| `technical.py` | TA-Lib wrapper: MA, EMA, Bollinger, MACD, KD, RSI, ADX, ATR, OBV |
| `chip_distribution.py` | Chip (holder) distribution analysis |
| `chip_cost.py` / `chip_health.py` / `chip_signals.py` | Chip cost, health score, and signal extraction |
| `major_players.py` | Smart money / major player capital flow |
| `lead_lag.py` | Lead-lag relationship detection |
| `seasonal.py` | Monthly/seasonal return statistics |
| `sector_rotation.py` | RRG, sector index ingestion, daily heatmap |
| `watch_graph.py` | Correlation graph construction (fusion, lead, chip weights) |
| `social_buzz.py` | News/social sentiment parsing |
| `correlation.py` | Correlation helpers |
| `day_trade.py` | Day-trade oriented analysis |

### Graph construction note

`backend/app/analysis/watch_graph.py` builds the network used by `/graph`. The fusion edge weight blends:

- Correlation
- Industry affinity
- Lead-lag signal
- Chip overlap

The default `edge_threshold` was reduced from `0.35` to `0.12` to match real-world FinMind weights (which often fall in `0.06~0.32`) and to avoid an empty graph in production where industry data is frequently missing.

## Crawlers

`backend/app/crawler/` abstracts data sources.

| Module | Source | Notes |
|--------|--------|-------|
| `finmind_client.py` | FinMind API v4 | Primary data source; requires `FINMIND_TOKEN` |
| `stock_price.py` | FinMind + yfinance fallback | Normalizes symbol suffixes (`.TW`, `.TWO`, `.US`) |
| `fundamental.py` | FinMind | Revenue, EPS, margins, debt ratios |
| `institutional.py` | FinMind | Foreign/institutional investor flows |
| `twse_public.py` | TWSE / TDCC public data | Free public data (dividends, shareholder distribution, etc.) |
| `sector_index.py` | FinMind / yfinance | Sector index prices |

Symbol normalization is centralized in `backend/app/data/us_symbols.py`. The UI search and API routes use it so users can type `2330`, `AAPL`, `AAPL.US`, etc.

## Machine learning

`backend/app/ml/predictor.py` (and `backend/app/api/ml.py`) implements a scikit-learn Random Forest classifier for BUY/SELL/HOLD signals. The model is trained on technical + fundamental + chip features and returns a signal with confidence.

## Backtest engine

`backend/app/backtest/engine.py` runs strategy simulations. Built-in strategies are in `backend/app/backtest/strategies/`:

- `ma_crossover` — MA crossover
- `macd_trend` — MACD trend
- `bollinger_breakout` — Bollinger breakout
- `rsi_reversion` — RSI mean reversion

Key recent enhancements:

- **Real trading costs** (`804f42f`): commission + slippage + Taiwan stock transaction tax, so results are NET.
- **Overfitting guard** (`e1e630f`): 70/30 in-sample/out-of-sample split with verdict labels.
- **MFE/MAE analysis** (`e1b990a`): per-trade max favorable / adverse excursion.

## Risk & trade control

`backend/app/risk/manager.py` is the central risk manager. `backend/app/api/risk.py` exposes:

- Market regime gauge (`/market-regime`) — offense/neutral/defense based on 0050 vs MA200.
- Position sizing (`/position-size`, `/kelly`, `/suggest-size`).
- Portfolio heat (`/portfolio-heat`).
- Scenario stress test (`/stress-test`).
- Equity curve (`/equity-curve`) used by risk distribution charts.
- Price alerts with Telegram push.
- Daily brief generation (`/daily-brief`) sent after market close.

## Notifications

`backend/app/notify/` contains LINE and Telegram adapters. Telegram is the actively maintained channel for risk summaries, price alerts, and daily briefs.

## Data & cache layer

| File | Purpose |
|------|---------|
| `backend/app/db/mongodb.py` | Async MongoDB connection |
| `backend/app/db/cache.py` | MongoDB-backed persistent cache + settings |
| `backend/app/db/cached.py` | Decorator for versioned caching |
| `backend/app/db/memcache.py` | In-memory cache for short-lived risk/graph/rotation data |

Cache keys should be versioned, e.g. `chip_analysis:v5:{symbol}`. Bump the version when the algorithm changes so stale cached results are invalidated.

## Scheduler

`backend/app/scheduler.py` runs a single async background task inside the FastAPI process:

- Triggers at a configurable Taiwan-time hour (default 15:00, after the 13:30 TWSE close).
- Skips weekends.
- Re-ingests sector rotation indices and optionally a watchlist (`AUTO_INGEST_SYMBOLS`).
- Clears memory cache keys `rotation:` and `graph:` after ingestion.

## Configuration & secrets

`backend/app/config/settings.py` uses `pydantic-settings` with `.env` support. Key variables:

- `FINMIND_TOKEN` — primary data source
- `MONGODB_URI` / `MONGODB_DB_NAME` — cache/log
- `LINE_NOTIFY_TOKEN` — LINE push
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Telegram push
- `GOOGLE_CLIENT_ID` — Google OAuth
- `ADMIN_SECRET` — JWT signing secret (random per-process if unset)
- `AUTO_INGEST_*` — scheduler tuning

`ADMIN_SECRET` is deliberately **not** hard-coded. If unset, `get_settings()` generates a random per-process secret and logs a warning, invalidating admin sessions on every restart.

## Source map

- `backend/app/main.py` — app assembly, routers, health, SPA fallback.
- `backend/app/api/__init__.py` — router exports.
- `backend/app/config/settings.py` — env-based settings.
- `backend/app/analysis/` — computational modules.
- `backend/app/crawler/` — data fetchers.
- `backend/app/backtest/` — backtest engine + strategies.
- `backend/app/ml/` — Random Forest predictor.
- `backend/app/risk/` — risk manager.
- `backend/app/notify/` — LINE/Telegram adapters.
- `backend/app/db/` — MongoDB/cache helpers.
- `backend/app/scheduler.py` — post-close auto-ingest scheduler.
