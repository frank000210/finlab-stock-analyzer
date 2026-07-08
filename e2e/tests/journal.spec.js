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
  await page.getByRole('button', { name: '加入' }).click()

  await expect(page.getByRole('heading', { name: /進行中/ })).toBeVisible()

  // Close at 120 -> R = (120-100)/(100-90) = 2.00
  await page.locator('.j-table input[type="number"]').first().fill('120')
  await page.getByRole('button', { name: '平倉' }).click()

  // Realized R in the closed table, and cumulative-R stat card.
  await expect(page.locator('.j-table')).toContainText('+2.00R')
  await expect(page.getByText('+2.00 R').first()).toBeVisible()
})
