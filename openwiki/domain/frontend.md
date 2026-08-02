# Frontend Domain & UI

The frontend is a Vue 3 single-page application (SPA) built with Vite. It is served as static files by the FastAPI backend in production, so all API calls are same-origin.

## Technology stack

| Layer | Choice |
|-------|--------|
| Framework | Vue 3 (Composition API with `<script setup>`) |
| Build tool | Vite 5 |
| State | Pinia |
| Routing | Vue Router 4 (history mode) |
| Charts | `lightweight-charts` for candle/line; D3 for custom visualizations |
| HTTP | `fetch` / page-local `apiGet` helpers |
| Styling | CSS variables in `frontend/src/assets/main.css` |

## Application bootstrap

`frontend/src/main.js`:

- Creates the Vue app.
- Installs Pinia and Router.
- Applies the saved theme before mounting to prevent flash.
- Registers the global `v-reveal` directive.
- Registers a global `app.config.errorHandler` that emits `finlab:app-error` events for `App.vue` to render as toasts.
- Registers `/sw.js` only in production for PWA support.

## Layout & global chrome

`frontend/src/App.vue` renders:

- `AppSidebar` — collapsible left sidebar with global search and navigation.
- `main` router view.
- Onboarding banner on first visit to `/`.
- `PageCounter` — global pageview counter.
- `QuickSwitcher` — Ctrl/Cmd+K command palette for pages and symbols.
- Global error toast stack.

## Routing

`frontend/src/router.js` uses `createWebHistory` and lazy-loads every view. Route groups:

- **Top-level pages**: `/`, `/overview`, `/decision`, `/graph`, `/rotation`, `/guide`, `/settings`, `/admin`, `/risk-sizing`, `/portfolio-heat`, `/journal`, `/monte-carlo`, `/price-alerts`, `/signals`, `/daily-brief`, `/command`, `/trade-dashboard`, `/ai-signals`, `/risk-monitor`, `/data-agent`, `/trade-approval`, `/signal-rules`.
- **Symbol-scoped pages**: `/stocks/:symbol`, `/stocks/:symbol/backtest`, `/stocks/:symbol/seasonal`, `/stocks/:symbol/lead-lag`, `/stocks/:symbol/major-players`, `/stocks/:symbol/chip`, `/stocks/:symbol/social-buzz`, `/stocks/:symbol/public-data`.

## Navigation

`frontend/src/components/AppSidebar.vue`:

- Collapsible sidebar (desktop) and slide-out drawer (mobile).
- Global stock search (`/api/v1/stocks/search`) with debounce.
- Selecting a stock updates `useStockStore` and, if currently on a symbol-scoped subpage, swaps the symbol while preserving the subpage.
- Grouped navigation links; CTA styling for high-priority entries.
- Google sign-in button for admin features.

## Design system

### CSS variables

Design tokens live in `frontend/src/assets/main.css`. Important families:

- Backgrounds: `--bg-primary`, `--bg-card`, `--card-inner-bg`
- Borders: `--border-color`, `--block-border-width`, etc.
- Text: `--text-primary`, `--text-secondary`, `--text-muted`
- Accents: `--accent-blue`, `--accent-blue-soft`
- Market colors: `--color-up`, `--color-down` (use these, never hard-code red/green)

### Styling rules

- Use CSS variables only.
- Apply `font-variant-numeric: tabular-nums` to numeric data.
- Prefer section/article semantics; animate with `v-reveal`.
- Mobile-first responsive layout via CSS Grid / Flexbox.

## Charts

- **Candlestick / line charts**: `lightweight-charts` (used in `AnalysisView.vue`, `ChipAnalysisView.vue`, etc.).
- **Custom statistical / network charts**: D3.
  - Treemap (`OverviewView`)
  - Box plot (`SeasonalView`)
  - PE/PB band + revenue growth (`PublicDataView`)
  - Histogram + KDE (`RiskMonitorView`)
  - Calendar heatmap (`AnalysisView`)
  - Correlation matrix heatmap (`GraphView`)
  - Horizon chart (`RotationView`)
  - Volume profile (`AnalysisView`)
  - Chord diagram (`RotationView`)
  - Sankey diagram (`TradeDashboardView`)

Most D3 charts are explicitly labeled "參考：D3 gallery - <name>" as a design attribution.

## State management

### `useStockStore` (`frontend/src/stores/stock.js`)

- Holds the current symbol and name.
- Persisted to `localStorage`.
- `symbol` and `name` are read-only `computed`; use `setStock(sym, name)` to mutate.
- Default symbol is `2330` (TSMC).

### `useAuthStore` (`frontend/src/stores/auth.js`)

- Admin Google OAuth state.
- `loginWithGoogle(idToken)` calls `/api/v1/auth/google/verify`.
- Stores `admin_token` and `admin_user` in `localStorage`.
- Provides `getAuthHeaders()` for `X-Admin-Token`.

## Key reusable components

| Component | File | Purpose |
|-----------|------|---------|
| `PageFocusBanner` | `frontend/src/components/PageFocusBanner.vue` | Observation-focus banner at the top of every non-home page |
| `AppSidebar` | `frontend/src/components/AppSidebar.vue` | Main navigation + search |
| `QuickSwitcher` | `frontend/src/components/QuickSwitcher.vue` | Ctrl/Cmd+K command palette |
| `PageCounter` | `frontend/src/components/PageCounter.vue` | Global pageview counter |
| `DataLineage` | `frontend/src/components/DataLineage.vue` | Data-source / staleness badges |

## Motion

`frontend/src/directives/reveal.js`:

- Adds scroll-triggered fade-in-up animation.
- Content is visible by default; JS only hides it when animation can run.
- Respects `prefers-reduced-motion`.
- Includes a 1.4s failsafe so hidden tabs/headless browsers never stay blank.
- Clears `will-change` after animation to avoid trapping `position: fixed` overlays.

## Theming

`frontend/src/composables/useTheme.js`:

- Reads/writes theme overrides to `localStorage`.
- Applies them to `:root` inline styles.
- Provides built-in presets and user-saved presets.
- Fields: page background, card background, block/card border widths and colors.

## Build & dev

- `npm run dev` — Vite dev server on `:5173`, proxies `/api` to `localhost:8000`.
- `npm run build` — production build into `frontend/dist`.
- `npm run preview` — preview the production build.

Production API base is empty (`API_BASE=''`) because the SPA is served from the same origin as FastAPI.

## PWA

Implemented in `5015bd7`:

- `frontend/public/manifest.webmanifest`
- Icons in `frontend/public/icons/`
- `frontend/public/sw.js` for offline app shell.
- Service worker registered only in production builds to avoid dev/HMR conflicts.

## Source map

- `frontend/src/main.js` — app bootstrap, error handler, SW registration.
- `frontend/src/App.vue` — layout, toasts, onboarding, global chrome.
- `frontend/src/router.js` — route table.
- `frontend/src/assets/main.css` — design tokens.
- `frontend/src/components/AppSidebar.vue` — navigation + search.
- `frontend/src/components/PageFocusBanner.vue` — observation banner.
- `frontend/src/components/QuickSwitcher.vue` — command palette.
- `frontend/src/directives/reveal.js` — scroll animation.
- `frontend/src/composables/useTheme.js` — theming.
- `frontend/src/stores/stock.js` / `auth.js` — state.
- `frontend/vite.config.js` — Vite config + dev proxy.
