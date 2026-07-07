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
