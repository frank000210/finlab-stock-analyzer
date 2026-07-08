// @ts-check
const { test, expect } = require('@playwright/test')

// Monte Carlo risk-of-ruin. 100% win rate is deterministic: never ruined.
test('風險模擬 runs and reports ruin probability', async ({ page }) => {
  await page.goto('/monte-carlo')
  await expect(page.getByRole('heading', { name: /風險模擬/ })).toBeVisible()

  const inputs = page.locator('.inputs input')
  await inputs.nth(0).fill('100') // win rate % -> every trade wins

  await page.getByRole('button', { name: '執行模擬' }).click()

  // Never ruined, always profitable.
  await expect(page.locator('.checklist li')).toContainText('破產機率 0.0%')
  await expect(page.locator('.checklist li')).toHaveClass(/ok/)
  await expect(page.locator('.rgrid')).toContainText('100.0%') // profitable probability
  await expect(page.locator('.hist-svg')).toBeVisible()
})
