// @ts-check
const { test, expect } = require('@playwright/test')

// On small screens the sidebar becomes an off-canvas drawer; the ☰ toggle
// must expose it so the risk/trading pages stay reachable on mobile.
test('mobile: 選單抽屜可開合並導頁', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await page.goto('/')

  const toggle = page.locator('.sidebar-mobile-toggle')
  await expect(toggle).toBeVisible()
  await expect(page.locator('.app-sidebar')).not.toHaveClass(/mobile-open/)

  await toggle.click()
  await expect(page.locator('.app-sidebar')).toHaveClass(/mobile-open/)
  await expect(page.locator('.app-sidebar')).toContainText('作戰台')

  // Navigating via a link works and closes the drawer.
  await page.locator('.app-sidebar .nav-item', { hasText: '交易日誌' }).click()
  await expect(page).toHaveURL(/\/journal/)
  await expect(page.locator('.app-sidebar')).not.toHaveClass(/mobile-open/)
})

test('mobile: 寬表首欄黏性固定 (D13)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/journal')
  await page.evaluate(() => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { id: 'm1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null, lots: 1, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null },
    ]))
  })
  await page.reload()

  const firstCell = page.locator('.j-table td.sym').first()
  await expect(firstCell).toBeVisible()
  expect(await firstCell.evaluate((el) => getComputedStyle(el).position)).toBe('sticky')
})

// P8：回測結果表／季節性熱力圖之前沒套用 .table-wrap，手機版橫向捲動時第
// 一欄（日期/年份）會捲出視窗外，看不出目前這列是哪一天/哪一年。
test('mobile: 回測交易明細表首欄黏性固定 (P8)', async ({ page }) => {
  test.setTimeout(180_000)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/stocks/2330/backtest')
  await page.getByRole('button', { name: /執行回測/ }).click()

  const firstCell = page.locator('.data-table tbody tr').first().locator('td').first()
  await expect(firstCell).toBeVisible({ timeout: 120_000 })
  expect(await firstCell.evaluate((el) => getComputedStyle(el).position)).toBe('sticky')
})

test('mobile: 季節性月報酬熱力圖首欄黏性固定 (P8)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/stocks/2330/seasonal')

  const firstCell = page.locator('.heatmap-table td.year-cell').first()
  await expect(firstCell).toBeVisible({ timeout: 20_000 })
  expect(await firstCell.evaluate((el) => getComputedStyle(el).position)).toBe('sticky')
})
