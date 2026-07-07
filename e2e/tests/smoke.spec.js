// @ts-check
const { test, expect } = require('@playwright/test')

// Smoke tests: each menu page loads and renders its real data / charts.
// These run against a live app (FinMind-backed), so data-heavy pages get
// generous timeouts and assert on stable, data-derived text.

test('home page loads', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/FinLab/i)
})

test('analysis page renders 2330 real data + chart', async ({ page }) => {
  await page.goto('/stocks/2330')
  await expect(page.getByText('台積電').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('多因子技術圖表')).toBeVisible()
})

test('graph page renders a non-empty network', async ({ page }) => {
  await page.goto('/graph')
  const badge = page.getByText(/已載入節點\s*\d+\s*個/)
  await expect(badge).toBeVisible({ timeout: 90_000 })
  // must not be the empty "0 個" state
  await expect(badge).not.toHaveText(/已載入節點\s*0\s*個/)
})

test('overview page renders sector treemap + radar', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByText('每日類股漲跌熱力圖')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('綜合評分雷達圖')).toBeVisible()
})

test('settings page loads', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: /設定/ })).toBeVisible()
})
