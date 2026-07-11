// @ts-check
const { test, expect } = require('@playwright/test')

// E14: dedicated frontend page for the C9 daily brief, so you can read it on
// the web instead of only via Telegram push.
test('盤後日報頁：顯示日報內容並可手動推播', async ({ page }) => {
  test.setTimeout(120_000)

  await page.request.post('/api/v1/risk/sync-watchlist', { data: { symbols: ['2330'] } })

  await page.goto('/daily-brief')
  await expect(page.getByRole('heading', { name: '盤後日報' })).toBeVisible()

  const briefText = page.locator('.brief-text')
  await expect(briefText).toContainText('盤後日報', { timeout: 90_000 })
  await expect(briefText).toContainText('2330')
  await expect(briefText).toContainText('非投資建議')

  await page.getByRole('button', { name: '推播到 Telegram' }).click()
  await expect(page.locator('.small')).toContainText(/已推播|未推播/, { timeout: 30_000 })
})
