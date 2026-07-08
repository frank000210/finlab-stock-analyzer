// @ts-check
const { test, expect } = require('@playwright/test')

// Trade Journal: record a trade, close it, verify realized R and stats.
test('交易日誌 records a trade, closes it, computes R and stats', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.clear())
  await page.reload()

  await expect(page.getByRole('heading', { name: /交易日誌/ })).toBeVisible()

  // Record a long: entry 100, stop 90 (1R = 10), target 130, 1 lot.
  await page.getByPlaceholder('代碼 2330').fill('2330')
  await page.getByPlaceholder('進場價').fill('100')
  await page.getByPlaceholder('停損價').fill('90')
  await page.getByPlaceholder('目標價(選填)').fill('130')
  await page.getByPlaceholder('張數').fill('1')
  await page.getByPlaceholder('型態(選填)').fill('突破')
  await page.getByRole('button', { name: '加入' }).click()

  await expect(page.getByRole('heading', { name: /進行中/ })).toBeVisible()

  // Close at 120 -> R = (120-100)/(100-90) = 2.00
  await page.locator('.j-table input[type="number"]').first().fill('120')
  await page.getByRole('button', { name: '平倉' }).click()

  // Realized R in the closed table, and cumulative-R stat card.
  await expect(page.locator('.j-table').first()).toContainText('+2.00R')
  await expect(page.getByText('+2.00 R').first()).toBeVisible()

  // Review analytics: R histogram + per-型態 stats (突破 group).
  await expect(page.getByRole('heading', { name: '複盤分析' })).toBeVisible()
  await expect(page.locator('.rhist-svg')).toBeVisible()
  await expect(page.locator('.analytics-grid')).toContainText('突破')
})

test('交易日誌 匯出 CSV', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    { id: 'x1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: 130, lots: 1, tag: '突破', openDate: '2026-07-01', status: 'closed', exit: 120, exitDate: '2026-07-05' },
  ])))
  await page.reload()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '匯出 CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/trade-journal.*\.csv/)
})
