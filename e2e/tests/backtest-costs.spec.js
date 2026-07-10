// @ts-check
const { test, expect } = require('@playwright/test')

// A1 rigor: backtest results must be net of real trading costs, and say so.
test('回測 computes with real costs and shows the cost strip', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/stocks/2330/backtest')

  // Cost inputs exist with Taiwan retail defaults.
  await expect(page.getByText('手續費率 %／邊（券商折扣後）')).toBeVisible()
  await expect(page.getByText(/滑價 %／邊/)).toBeVisible()

  await page.getByRole('button', { name: /執行回測/ }).click()

  // Results render with the cost disclosure (metrics are net of costs).
  await expect(page.locator('.cost-strip')).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('.cost-strip')).toContainText('交易成本已計入')
  await expect(page.locator('.cost-strip')).toContainText('證交稅 0.3%')
  await expect(page.getByText('年化報酬率')).toBeVisible()
})
