// @ts-check
const { test, expect } = require('@playwright/test')

// Command dashboard: ranked watchlist + risk-based suggested lots.
test('作戰台 ranks watchlist and computes suggested lots', async ({ page }) => {
  await page.route('**/api/v1/risk/watchlist-signals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          as_of: '2026-07-08',
          items: [
            { symbol: '2882', ok: true, price: 65, chg_pct: 1.0, trend: '多頭排列', rsi: 55, stop_dist_pct: 5, vol_ratio: 1.2, range_pos_pct: 60, setup_total: 72, setup_verdict: '進場條件佳', tags: [{ t: '多頭排列', tone: 'up' }] },
            { symbol: '2330', ok: true, price: 2440, chg_pct: -0.8, trend: '多頭排列', rsi: 56, stop_dist_pct: 5, vol_ratio: 0.6, range_pos_pct: 90, setup_total: 55, setup_verdict: '普通，需再確認', tags: [{ t: '多頭排列', tone: 'up' }] },
          ],
        },
      }),
    })
  })

  await page.goto('/command')
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882', '2330']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
  })
  await page.reload()

  await expect(page.locator('.cmd-table tbody tr')).toHaveCount(2)

  // budget = 1,000,000 * 1% = 10,000; 2882 risk/share = 65*5% = 3.25 -> ~3076 shares -> 3 lots.
  const row2882 = page.locator('.cmd-table tbody tr', { hasText: '2882' })
  await expect(row2882).toContainText('3 張')

  // score badge shown, best-first (2882 = 72).
  await expect(page.locator('.cmd-table .score').first()).toContainText('72')
})
