// @ts-check
const { test, expect } = require('@playwright/test')

// Verifies the loading spinner shown while "重算圖譜" (recompute graph) runs.
test('重算圖譜 shows a loading spinner while computing', async ({ page }) => {
  // Slow the timeline response so the loading state stays observable.
  await page.route('**/api/v1/graph/watchlist/timeline*', async (route) => {
    await new Promise((r) => setTimeout(r, 2000))
    await route.continue()
  })

  await page.goto('/graph')

  // Wait for the initial (also delayed) compute to settle: the button
  // returns to its idle label "重算圖譜" (it reads "運算中…" while busy).
  const recalcBtn = page.getByRole('button', { name: '重算圖譜', exact: true })
  await expect(recalcBtn).toBeVisible({ timeout: 90_000 })

  // Trigger a recompute; the spinner overlay + busy button must appear.
  await recalcBtn.click()
  await expect(page.locator('.canvas-loading')).toBeVisible()
  await expect(page.locator('.canvas-loading .loading-spinner')).toBeVisible()
  await expect(page.getByText(/重算圖譜中/)).toBeVisible()
  await expect(page.getByRole('button', { name: /運算中/ })).toBeVisible()

  // ...and it clears once the data returns.
  await expect(page.locator('.canvas-loading')).toBeHidden({ timeout: 90_000 })
})
