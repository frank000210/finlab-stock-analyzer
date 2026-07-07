# E2E tests (Playwright)

End-to-end tests that drive the running app in a real browser.

## Prerequisites
- The app must be running and reachable (default `http://localhost:8000`).
  Start it locally with `scripts/run-local.ps1`.
- One-time setup:
  ```bash
  cd e2e
  npm install
  npx playwright install chromium
  ```

## Run
```bash
cd e2e
npm test                      # against http://localhost:8000
BASE_URL=http://localhost:5173 npm test   # against a vite dev server
```

## Record new tests
```bash
cd e2e
npm run codegen               # opens Playwright codegen against the app
```

## Push gate
Per project workflow, code changes must pass `npm test` here (green) before
being pushed. See the repo handover notes.
