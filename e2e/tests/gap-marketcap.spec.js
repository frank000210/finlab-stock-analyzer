// @ts-check
const { test, expect } = require('@playwright/test')

// O1：市值分級 + 跳空缺口分級篩選（NotebookLM「Humbled Trader」盤前選股邏輯，
// 波段化調整為以市值分大/中型 3% vs 小型 10% 的跳空門檻，而非美股當沖門檻）。

test('作戰台 顯示跳空缺口警示標籤 (O1)', async ({ page }) => {
  await page.route('**/api/v1/risk/watchlist-signals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          as_of: '2026-07-14',
          items: [
            {
              symbol: '6488', name: '環球晶', ok: true, price: 55, chg_pct: 8.5, trend: '多頭排列', rsi: 68,
              stop_dist_pct: 6, vol_ratio: 2.1, range_pos_pct: 92, setup_total: 70, setup_verdict: '進場條件佳',
              tags: [{ t: '多頭排列', tone: 'up' }, { t: '跳空 +12.0%', tone: 'warn' }],
              gap_pct: 12.0, market_cap: 3_000_000_000, cap_tier: '小型',
            },
          ],
        },
      }),
    })
  })
  await page.route('**/api/v1/risk/market-regime', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { regime: 'offense', label: '進攻', risk_mult: 1.0, proxy: '0050', close: 60, ma200: 55, above_ma200: true, ma200_rising: true, mom20_pct: 2.5, as_of: '2026-07-14' } }),
    })
  })

  await page.goto('/command')
  await page.evaluate(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['6488'])))
  await page.reload()

  const row = page.locator('.cmd-table tbody tr', { hasText: '6488' })
  await expect(row.locator('.tag').filter({ hasText: '跳空' })).toBeVisible()
  await expect(row.locator('.tag').filter({ hasText: '跳空' })).toContainText('+12.0%')
})

test('部位風控 顯示市值分級卡片 (O1)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', name: '台積電', industry: '半導體業', price: 142, atr: 5, atr_period: 14, atr_pct: 3.5,
          suggested_stops: [{ label: '穩健', mult: 2, stop_price: 132, distance: 10, distance_pct: 7 }],
          market_cap: 3_690_000_000_000, cap_tier: '大型/中型',
          as_of: '2026-07-14', source: 'finmind',
        },
      }),
    })
  })
  await page.goto('/risk-sizing')
  await page.locator('.symbol-box input').fill('2330')
  await page.getByRole('button', { name: '查詢' }).click()

  await expect(page.locator('.mcard').filter({ hasText: '市值分級' })).toBeVisible()
  await expect(page.locator('.mcard').filter({ hasText: '市值分級' })).toContainText('大型/中型股')
  await expect(page.locator('.mcard').filter({ hasText: '市值分級' })).toContainText('3.69 兆')
})
