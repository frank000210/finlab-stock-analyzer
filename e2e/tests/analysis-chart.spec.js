// @ts-check
const { test, expect } = require('@playwright/test')

// ATR chandelier-exit trailing stop toggle on the analysis K-line chart.
test('分析 K 線有 ATR 移動停利切換且不報錯', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/stocks/2330')

  const toggle = page.locator('.ch-toggle input[type="checkbox"]')
  await expect(toggle).toBeVisible({ timeout: 60_000 })
  await expect(toggle).toBeChecked() // ATR trailing stop on by default

  // Chart canvas renders.
  await expect(page.locator('.price-chart canvas').first()).toBeVisible({ timeout: 60_000 })

  // Toggling off then on re-renders without throwing.
  await toggle.uncheck()
  await expect(toggle).not.toBeChecked()
  await toggle.check()
  await expect(toggle).toBeChecked()
  await expect(page.locator('.price-chart canvas').first()).toBeVisible()

  expect(errors).toEqual([])
})
