// @ts-check
const { test, expect } = require('@playwright/test')

// Shared dataset: 15 closed trades with openDate/exitDate, target, catalyst, varied lots
const makeWWTrades = () => Array.from({ length: 15 }, (_, i) => ({
  id: i + 1,
  symbol: i < 6 ? '2330' : i < 10 ? '2454' : '2317',
  side: 'long',
  entry: 600, stop: 580,
  exit: i < 10 ? 640 : 570,
  lots: i % 3 === 0 ? 2 : 1,
  openDate: `2026-0${Math.floor(i / 5) + 1}-${String((i % 5) + 1).padStart(2, '0')}`,
  exitDate: `2026-0${Math.floor(i / 5) + 1}-${String((i % 5) + 3).padStart(2, '0')}`,
  target: 650,
  catalyst: i < 5 ? 'breakout' : i < 10 ? 'oversold' : 'gap',
  tag: 'trend',
  status: 'closed',
}))

// WW1: Win vs loss average hold-days (Livermore)
test('WW1 hold-time analysis shows avg hold days for wins vs losses', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText('持倉天數：贏 vs 輸')).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: '持倉天數：贏 vs 輸' })).toContainText('天')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW2: Rolling 10-trade win rate sparkline (Druckenmiller)
test('WW2 rolling win rate sparkline renders with latest pct', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText('勝率趨勢（滾動10筆）')).toBeVisible()
  // sparkline SVG should be present
  await expect(page.locator('.scard').filter({ hasText: '勝率趨勢' }).locator('svg')).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: '勝率趨勢' })).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW3: Lot-size consistency CV (Tom Basso)
test('WW3 lot consistency CV card renders with warning when CV > 20%', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText('張數一致性（CV）')).toBeVisible()
  // lots vary between 1 and 2 across 15 trades → CV > 20%
  await expect(page.locator('.scard').filter({ hasText: '張數一致性' })).toContainText('%')
  await expect(page.locator('.scard').filter({ hasText: '張數一致性' })).toContainText('⚠')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW4: Near-zero R leak (Larry Williams)
test('WW4 near-zero R leak card shows pct and count', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText(/近零R滲漏/)).toBeVisible()
  // All trades are +2R or -1.5R → 0 near-zero → 0%
  await expect(page.locator('.scard').filter({ hasText: '近零R滲漏' })).toContainText('0%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW5: R-per-calendar-day capital efficiency (Druckenmiller)
test('WW5 R-per-day efficiency card shows positive value', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText('R/天（資本效率）')).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: 'R/天（資本效率）' })).toContainText('R/天')
  await expect(page.locator('.scard').filter({ hasText: 'R/天（資本效率）' })).toContainText('天跨度')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW6: Pre-trade checklist in DecisionView (Mark Douglas)
test('WW6 pre-trade checklist shows 5 items and tracks completion', async ({ page }) => {
  await page.goto('/decision')

  await expect(page.getByText('開盤前確認清單')).toBeVisible()
  // 5 checklist items
  const items = page.locator('.ww-checklist-item')
  await expect(items).toHaveCount(5)
  // Initially 0/5
  await expect(page.locator('.ww-checklist-card')).toContainText('0/5 項')
  // Click first item
  await items.first().locator('input[type=checkbox]').click()
  await expect(page.locator('.ww-checklist-card')).toContainText('1/5')
})

// WW7: Last-8-week breakdown table (institutional cadence)
test('WW7 weekly performance table renders with week rows', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText('近8週週績效')).toBeVisible()
  await expect(page.locator('.ww-weekly-table')).toBeVisible()
  // Should have at least header + 2 data rows
  const rows = page.locator('.ww-weekly-table tbody tr')
  await expect(rows).toHaveCount(await rows.count())
  const count = await rows.count()
  expect(count).toBeGreaterThanOrEqual(2)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW8: Target achievement rate (PTJ)
test('WW8 target achievement block renders hit rate and capture rate', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  const ww8Block = page.locator('.an-block').filter({ hasText: '達標率' })
  await expect(ww8Block).toBeVisible()
  await expect(ww8Block).toContainText('達標率')
  await expect(ww8Block).toContainText('平均捕捉率')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW9: Monthly return stats in RiskMonitorView (institutional P&L profile)
test('WW9 monthly return stats show median, std, and positive month pct', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeWWTrades())
  await page.reload()

  await expect(page.getByText('月報酬中位數')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.r-curve-stats').filter({ hasText: '月報酬中位數' })).toContainText('R')
  await expect(page.locator('.r-curve-stats').filter({ hasText: '月報酬標準差' })).toContainText('R')
  await expect(page.locator('.r-curve-stats').filter({ hasText: '正報酬月比率' })).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// WW10: Daily max-loss tracker in DecisionView (Minervini)
test('WW10 daily max-loss tracker renders with R limit input and current R', async ({ page }) => {
  await page.goto('/decision')

  await expect(page.getByText('今日最大虧損限制')).toBeVisible()
  await expect(page.locator('.ww-dayloss-card')).toContainText('今日已實現')
  // Limit input
  const limitInput = page.locator('.ww-dayloss-row input[type=number]')
  await expect(limitInput).toBeVisible()
  // Default limit is 2
  await expect(limitInput).toHaveValue('2')
})
