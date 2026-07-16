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

test('overview page renders single-stock radar', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByText('綜合評分雷達圖')).toBeVisible({ timeout: 60_000 })
})

// L2: sector-wide heatmap moved out of the single-stock overview page and
// into 類股輪動 (rotation), which already deals in sector/universe-level data.
test('rotation page renders sector treemap + RRG', async ({ page }) => {
  await page.goto('/rotation')
  await expect(page.getByText('每日類股漲跌熱力圖')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: 'RRG 輪動時鐘' })).toBeVisible()
})

test('settings page loads', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: /設定/ })).toBeVisible()
})

// P10：以下 4 頁之前完全沒有 e2e 覆蓋。
test('decision page renders dashboard shell', async ({ page }) => {
  await page.goto('/decision')
  await expect(page.getByRole('heading', { name: '今日決策面板' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: '市場脈動總覽' })).toBeVisible()
})

test('ai-signals page renders signal list', async ({ page }) => {
  await page.goto('/ai-signals')
  await expect(page.getByRole('heading', { name: 'AI 交易信號' })).toBeVisible({ timeout: 60_000 })
})

test('chip analysis page renders 2330 data', async ({ page }) => {
  await page.goto('/stocks/2330/chip')
  await expect(page.getByRole('heading', { name: '籌碼分析' })).toBeVisible({ timeout: 60_000 })
})

test('admin page shows login gate when not authenticated', async ({ page }) => {
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: /使用 Google 登入/ })).toBeVisible()
})

// R10：以下 6 頁之前完全沒有 e2e 覆蓋。
test('graph01 page renders watchlist graph shell', async ({ page }) => {
  await page.goto('/graph01')
  await expect(page.getByRole('heading', { name: '觀察股關聯圖' })).toBeVisible({ timeout: 60_000 })
})

test('lead-lag page renders 2330 analysis', async ({ page }) => {
  await page.goto('/stocks/2330/lead-lag')
  await expect(page.getByRole('heading', { name: /領先\/落後分析/ })).toBeVisible({ timeout: 60_000 })
})

test('major-players page renders 2330 analysis', async ({ page }) => {
  await page.goto('/stocks/2330/major-players')
  await expect(page.getByRole('heading', { name: /主力動向分析/ })).toBeVisible({ timeout: 60_000 })
})

test('public-data page renders 2330 data', async ({ page }) => {
  await page.goto('/stocks/2330/public-data')
  await expect(page.getByRole('heading', { name: /公開資訊/ })).toBeVisible({ timeout: 60_000 })
})

test('data-agent page renders crawler/news check shell', async ({ page }) => {
  await page.goto('/data-agent')
  await expect(page.getByRole('heading', { name: '資料爬蟲與新聞檢查' })).toBeVisible({ timeout: 60_000 })
})

test('signal-rules page renders rule list', async ({ page }) => {
  await page.goto('/signal-rules')
  await expect(page.getByRole('heading', { name: '信號規則編輯器' })).toBeVisible({ timeout: 60_000 })
})
