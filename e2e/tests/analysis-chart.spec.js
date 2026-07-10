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

test('分析 K 線顯示進場評分徽章', async ({ page }) => {
  await page.goto('/stocks/2330')
  await expect(page.locator('.setup-badge')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.setup-badge')).toContainText('進場評分')
})

test('分析 K 線顯示資料血統徽章 (A2)', async ({ page }) => {
  await page.goto('/stocks/2330')
  const badge = page.locator('.lineage')
  await expect(badge).toBeVisible({ timeout: 60_000 })
  await expect(badge).toContainText('📅')
  await expect(badge).toContainText('FinMind') // 主源正常時應標 FinMind
})

test('分析 K 線可切換 日/週/月 時間框架', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/stocks/2330')
  await expect(page.locator('.price-chart canvas').first()).toBeVisible({ timeout: 60_000 })

  // 切到週線：price API 應帶 period=1w，圖表重繪不報錯
  const weeklyReq = page.waitForRequest((r) => r.url().includes('/price?') && r.url().includes('period=1w'), { timeout: 30_000 })
  await page.getByRole('button', { name: '週', exact: true }).click()
  await weeklyReq
  await expect(page.locator('.price-chart canvas').first()).toBeVisible({ timeout: 60_000 })

  // 切回日線
  await page.getByRole('button', { name: '日', exact: true }).click()
  await expect(page.locator('.price-chart canvas').first()).toBeVisible({ timeout: 60_000 })

  expect(errors).toEqual([])
})
