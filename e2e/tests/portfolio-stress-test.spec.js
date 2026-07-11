// @ts-check
const { test, expect } = require('@playwright/test')

// B8: 情境壓測 — apply a hypothetical crash scenario to current positions
// and show the resulting loss, distinct from the "if stops execute normally" heat number.
test('投組風險 情境壓測顯示各情境下的虧損試算', async ({ page }) => {
  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('portfolio_heat_positions', JSON.stringify([
      { symbol: '2330', name: '台積電', industry: '半導體業', entry: 1000, stop: 950, lots: 1, price: 1000 },
    ]))
  })
  await page.reload()

  await expect(page.getByRole('heading', { name: /情境壓測/ })).toBeVisible()

  // Default scenario -10%: 1 lot (1000 shares) * 1000 * -10% = -100,000 loss.
  await expect(page.locator('.stress-table')).toContainText('900.00')
  await expect(page.locator('.scard').filter({ hasText: '情境總虧損' }).locator('.sval')).toHaveText('-100,000')

  // Switch to -20% scenario: loss doubles to -200,000.
  await page.getByRole('button', { name: '大盤重挫 -20%（熊市）' }).click()
  await expect(page.locator('.scard').filter({ hasText: '情境總虧損' }).locator('.sval')).toHaveText('-200,000')

  // Stop-based scenario uses the stop price (950) directly: loss = -50,000.
  await page.getByRole('button', { name: '停損全數跳空觸發' }).click()
  await expect(page.locator('.scard').filter({ hasText: '情境總虧損' }).locator('.sval')).toHaveText('-50,000')
})
