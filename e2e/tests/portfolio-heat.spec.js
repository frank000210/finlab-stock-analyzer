// @ts-check
const { test, expect } = require('@playwright/test')

// Portfolio Heat: add a position and confirm total risk heat is computed.
test('投組風險 adds a position and computes total heat', async ({ page }) => {
  await page.goto('/portfolio-heat')
  await page.evaluate(() => localStorage.clear())
  await page.reload()

  await expect(page.getByRole('heading', { name: /投組總風險/ })).toBeVisible()

  // Starts empty.
  await expect(page.locator('.scard.heat .sval')).toHaveText('0.00%')

  // Add a position (1 lot of 2330, 130 risk/share -> 130k risk on 1M = 13%).
  await page.getByPlaceholder('代碼 2330').fill('2330')
  await page.getByPlaceholder('進場價').fill('2440')
  await page.getByPlaceholder('停損價').fill('2310')
  await page.getByPlaceholder('張數').fill('1')
  await page.getByRole('button', { name: '加入' }).click()

  // Row appears and total heat becomes non-zero.
  await expect(page.locator('.pos-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.pos-table')).toContainText('2330')
  await expect(page.locator('.scard.heat .sval')).not.toHaveText('0.00%')

  // Sector concentration section renders.
  await expect(page.getByRole('heading', { name: /產業集中度/ })).toBeVisible()
})

test('投組風險 warns on highly-correlated positions', async ({ page }) => {
  // Deterministic correlation payload (2330 & 2454 highly correlated).
  await page.route('**/api/v1/risk/correlation*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbols: ['2330', '2454'],
          matrix: [[1.0, 0.85], [0.85, 1.0]],
          pairs: [{ a: '2330', b: '2454', corr: 0.85 }],
          high_pairs: [{ a: '2330', b: '2454', corr: 0.85 }],
          high_threshold: 0.7,
          avg_abs_corr: 0.85,
          days: 60,
        },
      }),
    })
  })

  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.setItem('portfolio_heat_account', '3000000')
    localStorage.setItem('portfolio_heat_positions', JSON.stringify([
      { symbol: '2330', name: '台積電', industry: '半導體業', entry: 2440, stop: 2380, lots: 2, price: 2440 },
      { symbol: '2454', name: '聯發科', industry: '半導體業', entry: 1400, stop: 1360, lots: 2, price: 1400 },
    ]))
  })
  await page.reload()

  await page.getByRole('button', { name: /分析相關性/ }).click()

  // High-correlation warning + matrix render.
  await expect(page.locator('.hp-warn')).toContainText('0.85')
  await expect(page.getByText(/實質同一注/)).toBeVisible()
  await expect(page.locator('.corr-matrix table')).toBeVisible()
})

test('投組風險 從觀察清單匯入 adds watchlist symbols', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', name: '台積電', industry: '半導體業', price: 2440,
          atr: 65, atr_period: 14, atr_pct: 2.66,
          suggested_stops: [{ label: '穩健', mult: 2, stop_price: 2310, distance: 130, distance_pct: 5.33 }],
          as_of: '2026-07-07',
        },
      }),
    })
  })
  await page.route('**/api/v1/risk/correlation*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbols: ['2330', '2454'], matrix: [[1, 0.4], [0.4, 1]], pairs: [{ a: '2330', b: '2454', corr: 0.4 }], high_pairs: [], high_threshold: 0.7, avg_abs_corr: 0.4, days: 60 } }),
    })
  })

  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2330', '2454']))
  })
  await page.reload()

  await page.getByRole('button', { name: /從觀察清單匯入/ }).click()

  await expect(page.locator('.pos-table tbody tr')).toHaveCount(2)
  await expect(page.locator('.pos-table')).toContainText('2330')
  await expect(page.locator('.pos-table')).toContainText('2454')
})

test('投組風險 補齊資料失敗時顯示警示，不悄悄留在現價 0 (P7)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify({ detail: '查詢失敗' }) })
  })
  await page.goto('/portfolio-heat')
  await page.evaluate(() => localStorage.clear())
  await page.reload()

  await page.getByPlaceholder('代碼 2330').fill('2330')
  await page.getByPlaceholder('進場價').fill('2440')
  await page.getByPlaceholder('停損價').fill('2310')
  await page.getByPlaceholder('張數').fill('1')
  await page.getByRole('button', { name: '加入' }).click()

  await expect(page.locator('.pos-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.enrich-warn')).toBeVisible()
  await expect(page.locator('.error-text')).toContainText('補齊名稱/現價失敗')
})

test('投組風險 推播風險摘要 (mocked telegram relay)', async ({ page }) => {
  await page.route('**/api/v1/risk/notify', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, sent: true, error: '' }) })
  })
  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('portfolio_heat_positions', JSON.stringify([
      { symbol: '2330', name: '台積電', industry: '半導體業', entry: 2440, stop: 2380, lots: 2, price: 2440 },
    ]))
  })
  await page.reload()

  await page.getByRole('button', { name: /推播風險摘要/ }).click()
  await expect(page.locator('.notify-row')).toContainText('已推播')
})
