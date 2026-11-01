// @ts-check
const { defineConfig, devices } = require('@playwright/test')

/**
 * Playwright config. Tests run against an already-running app.
 * Override the target with BASE_URL, e.g.
 *   BASE_URL=http://localhost:8000 npm test
 */
module.exports = defineConfig({
  testDir: './tests',
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 4,
  retries: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 25_000,
    navigationTimeout: 45_000,
    // 擋掉外部字型 CDN（Google Fonts、jsdelivr 的霞鶩文楷）：頁面 load 事件要等這幾十個字型子集下載完，
    // 外網一慢，跟功能無關的 page.goto 就會 45 秒逾時。測試只看版面與文字，不需要真字型。
    launchOptions: {
      args: [
        '--host-resolver-rules=MAP fonts.googleapis.com ~NOTFOUND, MAP fonts.gstatic.com ~NOTFOUND, MAP cdn.jsdelivr.net ~NOTFOUND',
      ],
    },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
