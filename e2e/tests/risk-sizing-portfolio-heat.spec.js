// @ts-check
const { test, expect } = require('@playwright/test')

// F6: 部位風控 previously sized a single symbol in isolation — no visibility
// into whether adding this position would push the whole portfolio's risk
// heat (投組風險/Portfolio Heat) over the recommended ceiling. This cross-
// references the existing portfolio_heat_positions so that risk is visible
// at the moment of sizing, not only after the fact on a different page.
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', name: '台積電', industry: '半導體業', price: 2440,
          atr: 65, atr_period: 14, atr_pct: 2.66, as_of: '2026-07-11', source: 'finmind',
          suggested_stops: [{ label: '穩健', mult: 2, stop_price: 2310, distance: 130, distance_pct: 5.33 }],
        },
      }),
    })
  })
})

test('部位風控 加上這筆會讓投組總風險熱度超標時顯示警示 (F6)', async ({ page }) => {
  await page.goto('/risk-sizing')
  await page.evaluate(() => {
    // 既有部位風險金額 10,000,000（獨立於這筆試算的代碼），本身就已經很重。
    localStorage.setItem('portfolio_heat_positions', JSON.stringify([
      { symbol: '2454', name: '聯發科', industry: '半導體業', entry: 100, stop: 90, lots: 1000, price: 100 },
    ]))
  })
  await page.reload()

  await page.getByRole('spinbutton').first().fill('50000000')
  await expect(page.locator('.rcard.hl strong')).not.toContainText('0 張')

  const projected = page.locator('.checklist li', { hasText: '投組總風險熱度' })
  await expect(projected).toBeVisible()
  await expect(projected).toHaveClass(/bad/)
  await expect(projected).toContainText('1 筆既有部位')
})

test('部位風控 沒有投組部位時不顯示投組總風險熱度提示 (F6)', async ({ page }) => {
  await page.goto('/risk-sizing')
  await page.evaluate(() => localStorage.removeItem('portfolio_heat_positions'))
  await page.reload()

  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.checklist li', { hasText: '投組總風險熱度' })).toHaveCount(0)
})

// E1: 交易日誌的進行中部位（沒有重複記錄在投組風險頁時）也是真實曝險，
// 沒有手動部位時過去完全不顯示這個提示，會漏看日誌裡的曝險。
test('部位風控 只有交易日誌部位、沒有手動投組部位時也顯示投組總風險熱度 (E1)', async ({ page }) => {
  await page.goto('/risk-sizing')
  await page.evaluate(() => {
    localStorage.removeItem('portfolio_heat_positions')
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { id: 'j1', symbol: '2454', name: '聯發科', side: 'long', entry: 100, stop: 90, target: null, lots: 1000, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null },
    ]))
  })
  await page.reload()

  await page.getByRole('spinbutton').first().fill('50000000')
  await expect(page.locator('.rcard.hl strong')).not.toContainText('0 張')

  const projected = page.locator('.checklist li', { hasText: '投組總風險熱度' })
  await expect(projected).toBeVisible()
  await expect(projected).toContainText('0 筆既有部位')
  await expect(projected).toContainText('交易日誌 1 筆進行中部位')
})
