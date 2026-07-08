// @ts-check
const { test, expect } = require('@playwright/test')

// Watchlist signal digest (endpoint mocked for determinism).
test('觀察清單訊號 shows signal cards with tags', async ({ page }) => {
  await page.route('**/api/v1/risk/watchlist-signals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          as_of: '2026-07-07',
          items: [
            { symbol: '2330', ok: true, price: 2440, chg_pct: -0.8, trend: '多頭排列', rsi: 55.2, stop_dist_pct: 5.3, vol_ratio: 1.8, range_pos_pct: 88, setup_total: 78, setup_verdict: '進場條件佳', tags: [{ t: '多頭排列', tone: 'up' }, { t: '爆量 1.8×', tone: 'warn' }] },
            { symbol: '2454', ok: true, price: 1400, chg_pct: 1.2, trend: '盤整', rsi: 48, stop_dist_pct: 6.1, vol_ratio: 0.9, range_pos_pct: 50, setup_total: 42, setup_verdict: '條件不佳，觀望', tags: [{ t: '盤整', tone: 'flat' }] },
          ],
        },
      }),
    })
  })

  await page.goto('/signals')
  await page.evaluate(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['2330', '2454'])))
  await page.reload()

  await expect(page.locator('.cards .scard')).toHaveCount(2)
  await expect(page.locator('.cards')).toContainText('多頭排列')
  await expect(page.locator('.cards')).toContainText('爆量 1.8×')

  // Setup-score badges rendered (one per card).
  await expect(page.locator('.cards .score')).toHaveCount(2)
  await expect(page.locator('.cards .score.good').first()).toContainText('78')
})
