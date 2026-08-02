# Development Workflow & Conventions

This page captures the project's development SOP. The canonical human docs are `docs/00-開發流程.md`, `docs/04-開發指引.md`, and `docs/06-頁面觀測重點與改動清單.md`.

## Development philosophy

- **One verifiable increment per round**: plan → implement → local build/import check → commit → push → deploy → verify online.
- **Conventional Commits**: `feat(...)`, `fix(...)`, `docs(...)`, `chore(...)`.
- **Traditional Chinese** for all user-facing copy.
- **No hard-coded secrets**: everything goes through `backend/app/config/settings.py` from environment variables.

## Starting local development

### Backend

```powershell
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Copy .env.example -> .env and fill FINMIND_TOKEN / GOOGLE_CLIENT_ID / MONGODB_URI
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

- MongoDB is optional: the app gracefully skips cache/logging if Mongo is unavailable.
- Health check: `GET http://localhost:8000/api/health`
- API docs: `http://localhost:8000/api/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev     # http://localhost:5173, proxied to backend :8000
```

### One-command local start (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

This starts MongoDB and injects `FINMIND_TOKEN` from the Windows environment.

## Pre-commit verification

Before every commit, both of these must pass:

```powershell
cd frontend; npm run build
cd ..\backend; python -c "from app.main import app; print('OK')"
```

Do not commit if either fails.

## Backend conventions

### Adding an API endpoint

1. Write a pure computation function in `backend/app/analysis/` (or `ml/`, `risk/`, `backtest/`, etc.). It should be unit-testable without HTTP.
2. Create or extend an `APIRouter` in `backend/app/api/<feature>.py` with prefix `/api/v1/<feature>`.
3. Return the unified shape `{"success": True, "data": ...}`.
4. Export the router in `backend/app/api/__init__.py` and include it in `backend/app/main.py`.
5. Use a versioned cache key when caching heavy results, e.g. `f"chip_analysis:v5:{symbol}:{days}"`. Bump the version when the algorithm changes.
6. Parallelize independent fetches with `asyncio.gather(..., return_exceptions=True)` and handle exceptions individually so one bad source does not break the whole response.

### Defensive data handling

- `SafeJSONResponse` in `backend/app/main.py` cleans NaN/Inf and numpy types before serialization, but analysis code should still prefer native Python scalars.
- **Fail soft**: if one data source is down, degrade gracefully and return whatever is available.

## Frontend conventions

### Adding a page

1. Create `frontend/src/views/XxxView.vue`.
2. Register a lazy route in `frontend/src/router.js`.
3. Add a navigation entry in `frontend/src/components/AppSidebar.vue` if the page belongs in the sidebar.
4. Place a `PageFocusBanner` as the first child of the page root:

```html
<div class="xxx-page">
  <PageFocusBanner text="這頁要讓使用者看懂什麼" />
  ...
</div>
```

5. Update `docs/06-頁面觀測重點與改動清單.md`.

### Fetching data

Use the page-local `apiGet` helper and **always validate the response shape** before using it:

```js
const payload = await apiGet(`/api/v1/stocks/${symbol}/chip-score`)
if (payload && typeof payload === 'object' && 'score' in payload) {
  // use it
}
```

### Styling rules

- Use CSS variables from `frontend/src/assets/main.css`; do not hard-code colors.
- Use `--color-up` / `--color-down` for gains/losses.
- Apply `font-variant-numeric: tabular-nums` to numbers.
- Use `lightweight-charts` for financial time-series; use D3 for custom statistical/network visualizations.
- Apply `v-reveal` for enter animations. Content must be visible by default; the directive only enhances it.

## Page observation focus (觀測重點)

Every non-home page has **exactly one observation focus** — one sentence describing what the user should learn from the page.

- Before designing a page, write the observation focus.
- Put it in a `PageFocusBanner` at the top of the view.
- Do not add charts that answer a different page's question.
- The full mapping of route → observation focus is maintained in `docs/06-頁面觀測重點與改動清單.md`.

## Git workflow

1. Pull latest `master`.
2. Create a feature branch or work directly on `master` if authorized.
3. Make one focused commit per increment.
4. Run build + backend import checks.
5. Push and deploy to Zeabur.
6. Verify on the live site.

## Common pitfalls

- **Sandbox environment issues** (from `交接SOP.md`): in some Cowork-like sandbox environments, `Edit` tool writes may not be immediately visible to bash; use Python scripts to rewrite files before `git add`, and verify with `git ls-files -s` vs `git hash-object`.
- **Frontend build in sandbox**: may fail due to missing `@rollup/rollup-linux-x64-gnu`; verify with `@vue/compiler-sfc` syntax check instead, and let the user run `npm run build` on native Windows.
- **API 404 vs SPA fallback**: a missing `/api/*` path intentionally returns 404 (not `index.html`) so API failures are not hidden.

## Source map

- `docs/00-開發流程.md` — overall web-dev SOP.
- `docs/04-開發指引.md` — detailed backend/frontend conventions.
- `docs/06-頁面觀測重點與改動清單.md` — route → observation focus mapping.
- `frontend/src/components/PageFocusBanner.vue` — banner component.
- `frontend/src/directives/reveal.js` — scroll animation directive.
- `backend/app/config/settings.py` — env-based settings.
