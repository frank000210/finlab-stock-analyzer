// @ts-check
const { test, expect } = require('@playwright/test')

// On small screens the secondary nav is hidden; the ☰ 更多 menu must expose it
// so the risk/trading pages stay reachable on mobile.
test('mobile: 更多 menu exposes the secondary nav pages', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await page.goto('/')

  const toggle = page.locator('.more-toggle')
  await expect(toggle).toBeVisible()
  await expect(page.locator('.secondary-nav')).toBeHidden() // collapsed by default

  await toggle.click()
  await expect(page.locator('.secondary-nav')).toBeVisible()
  await expect(page.locator('.secondary-nav')).toContainText('作戰台')

  // Navigating via a link works and closes the menu.
  await page.locator('.secondary-nav a', { hasText: '交易日誌' }).click()
  await expect(page).toHaveURL(/\/journal/)
  await expect(page.locator('.secondary-nav')).toBeHidden()
})
