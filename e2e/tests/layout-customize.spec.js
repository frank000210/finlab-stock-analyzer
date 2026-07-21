// @ts-check
const { test, expect } = require('@playwright/test')

// Y10：作戰台/總覽頁面版面自訂——
// 總覽頁：6 個維度卡片可隱藏＋排序（存 localStorage，重新整理後仍生效）。
// 作戰台：3 個提示條可隱藏（純顯示層級，不影響底層紀律檢查邏輯）。

test('總覽頁：隱藏一個維度卡片，重新整理後仍隱藏 (Y10)', async ({ page }) => {
  await page.route('**/api/v1/stocks/*/seasonal*', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { patterns: [] } }) }))
  await page.route('**/api/v1/stocks/*/lead-lag*', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { peak_correlation: 0.5, optimal_lag: 3, beta: { value: 1 }, interpretation: { direction: '領先' } } }) }))
  await page.route('**/api/v1/stocks/*/major-players*', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { score: 10, verdict: '中性', confidence: 60, signals: [] } }) }))
  await page.route('**/api/v1/stocks/*/social-buzz', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { buzz_score: 40, buzz_level: '普通', trend_label: '持平', ptt: { post_count: 1 }, news: { article_count: 1 } } }) }))
  await page.route('**/api/v1/stocks/*/public-data', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { announcements: [], dividends: [] } }) }))
  await page.route('**/api/v1/stocks/*/price*', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { items: [] } }) }))

  await page.goto('/overview')
  await page.getByRole('button', { name: '🧩 版面設定' }).click()

  const panel = page.locator('.layout-panel')
  await expect(panel).toBeVisible()
  const seasonalCheckbox = panel.locator('.layout-item', { hasText: '季節性分析' }).locator('input[type="checkbox"]')
  await expect(seasonalCheckbox).toBeChecked()
  await seasonalCheckbox.uncheck()

  await expect(page.locator('.summary-card', { hasText: '季節性分析' })).toBeHidden()

  await page.reload()
  await page.getByRole('button', { name: '🧩 版面設定' }).click()
  const seasonalCheckboxAfter = page.locator('.layout-item', { hasText: '季節性分析' }).locator('input[type="checkbox"]')
  await expect(seasonalCheckboxAfter).not.toBeChecked()
  await expect(page.locator('.summary-card', { hasText: '季節性分析' })).toBeHidden()
})

test('總覽頁：上移一個維度卡片改變排序', async ({ page }) => {
  await page.route('**/api/v1/stocks/*/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { items: [] } }) }))

  await page.goto('/overview')
  await page.getByRole('button', { name: '🧩 版面設定' }).click()

  const items = page.locator('.layout-item')
  const firstLabelBefore = await items.nth(0).locator('label').textContent()
  const secondItem = items.nth(1)
  await secondItem.locator('button[aria-label="上移"]').click()

  const firstLabelAfter = await page.locator('.layout-item').nth(0).locator('label').textContent()
  expect(firstLabelAfter?.trim()).not.toEqual(firstLabelBefore?.trim())
})

test('作戰台：隱藏市場體制提示條 (Y10)', async ({ page }) => {
  await page.route('**/api/v1/risk/market-regime', r => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ data: { regime: 'neutral', label: '中性', close: 17000, ma200: 16500, above_ma200: true, ma200_rising: true, mom20_pct: 1.2, risk_mult: 1 } }),
  }))
  await page.route('**/api/v1/risk/watchlist-signals*', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { items: [], as_of: '' } }) }))
  await page.route('**/api/v1/risk/sync-watchlist', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) }))

  await page.goto('/command')
  await expect(page.locator('.regime-strip')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('button', { name: '🧩 版面設定' }).click()
  await page.locator('.layout-strip-item', { hasText: '市場體制' }).locator('input[type="checkbox"]').uncheck()

  await expect(page.locator('.regime-strip')).toBeHidden()
  // 熔斷提示條仍在（沒被連動隱藏）
  await expect(page.locator('.loss-limit-strip')).toBeVisible()
})
