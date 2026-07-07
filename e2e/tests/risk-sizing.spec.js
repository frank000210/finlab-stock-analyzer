// @ts-check
const { test, expect } = require('@playwright/test')

// Position & Risk Sizing tool: loads market data (price/ATR) and computes a
// risk-based position size.
test('部位風控 loads market data and computes a position', async ({ page }) => {
  await page.goto('/risk-sizing')

  await expect(page.getByRole('heading', { name: /部位風控試算/ })).toBeVisible()

  // Market data (current price) loads from the backend.
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.mval').first()).not.toHaveText('—')

  // Sizing result renders (defaults: entry=price, stop=ATR-based).
  await expect(page.locator('.rcard.hl')).toContainText('張', { timeout: 20_000 })
  await expect(page.getByText('每股風險')).toBeVisible()

  // A large account should size at least one lot.
  await page.getByRole('spinbutton').first().fill('50000000')
  await expect(page.locator('.rcard.hl strong')).not.toContainText('0 張')

  // Risk-discipline checklist is shown.
  await expect(page.locator('.checklist li').first()).toBeVisible()
})
