// @ts-check
const { test, expect } = require('@playwright/test')

// A3: overfitting guard — walk-forward 70/30 in-sample/out-of-sample split
// on the same fetched price data, same strategy/params.
test('回測顯示樣本外驗證（過擬合防護）面板', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/stocks/2330/backtest')

  // Default date range (2021-01-01 ~ today) is long enough for a 70/30 split.
  await page.getByRole('button', { name: /執行回測/ }).click()

  const card = page.locator('.overfit-card')
  await expect(card).toBeVisible({ timeout: 120_000 })
  await expect(card).toContainText('樣本外驗證')

  // Either a full IS/OOS comparison, or an explicit insufficient-data note —
  // either way the guard must say something, never silently omit itself.
  const hasSplit = await page.locator('.of-grid').isVisible().catch(() => false)
  if (hasSplit) {
    await expect(card).toContainText('樣本內')
    await expect(card).toContainText('樣本外')
    await expect(card).toContainText('切分日')
    await expect(page.locator('.of-verdict')).toBeVisible()
  } else {
    await expect(card).toContainText(/略過過擬合檢查|太少無法判斷/)
  }
})
