// @ts-check
const { test, expect } = require('@playwright/test')

// T-027：個股橫向切換條（StockContextBar）、頁內區段錨點、無重掛主題切換、
// 等寬金融數字、骨架屏與首頁動線優化回歸測試。

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('finlab_onboarded', '1') } catch (e) { /* ignore */ }
  })
})

test('StockContextBar：9 大子頁切換保留代號、同頁換股、觀察清單同步與部位/警報捷徑', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    const url = new URL(route.request().url())
    const q = url.searchParams.get('q') || ''
    const items = q.includes('2317') || q.includes('鴻海')
      ? [{ symbol: '2317', name_zh: '鴻海' }]
      : q.includes('2330')
        ? [{ symbol: '2330', name_zh: '台積電' }]
        : []
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items } }),
    })
  })
  await page.route('**/api/v1/stocks/*/seasonal*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { patterns: [], yearly_matrix: [], raw_monthly: [], month_stats: [], quarterly_stats: [] },
      }),
    })
  })
  await page.route('**/api/v1/stocks/*/lead-lag*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          optimal_lag: 0,
          peak_correlation: 0.7,
          concurrent_correlation: 0.7,
          interpretation: { direction: '同步', direction_detail: '同步', suggestion: '觀察', correlation_strength: '高', consistency_pct: 80 },
          beta: { value: 1.1, interpretation: '略高於大盤', r_squared: 0.5 },
          correlations: [],
          rolling_lead_lag: [],
        },
      }),
    })
  })

  await page.goto('/stocks/2330/seasonal')
  const bar = page.getByTestId('stock-context-bar')
  await expect(bar).toBeVisible()
  await expect(bar.locator('.ctx-tab')).toHaveCount(9)
  await expect(bar.locator('.ctx-tab.active')).toHaveText('季節性')

  // 快速換股留在同一子頁（seasonal）
  await bar.getByTestId('ctx-switch-input').fill('2317')
  await bar.getByTestId('ctx-switch-btn').click()
  await expect(page).toHaveURL(/\/stocks\/2317\/seasonal$/)
  await expect(bar.locator('.ctx-symbol')).toHaveText('2317')

  // 點選另一子頁膠囊保留當前代號 2317
  await bar.locator('.ctx-tab[data-subpage="lead-lag"]').click()
  await expect(page).toHaveURL(/\/stocks\/2317\/lead-lag$/)
  await expect(bar.locator('.ctx-tab.active')).toHaveText('領先落後')

  // 觀察清單切換同步至 finlab_watchlist
  const wlBtn = bar.getByTestId('ctx-watchlist-btn')
  await expect(wlBtn).toContainText('觀察清單')
  await wlBtn.click()
  await expect(wlBtn).toContainText('已追蹤')
  const wl = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist') || '[]'))
  expect(wl).toContain('2317')

  // 設價格警報捷徑帶入 symbol query 並自動預填表單
  await page.route('**/api/v1/risk/alerts*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await bar.getByTestId('ctx-price-alerts-link').click()
  await expect(page).toHaveURL(/\/price-alerts\?symbol=2317$/)
  await expect(page.getByPlaceholder('代碼 2330')).toHaveValue('2317')
})

test('HomeView：6 張特色卡皆為真實連結、搜尋防呆不盲導壞頁、回訪交易者前置快捷區', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    const url = new URL(route.request().url())
    const q = url.searchParams.get('q') || ''
    const items = q.includes('台積') ? [{ symbol: '2330', name_zh: '台積電' }] : []
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items } }),
    })
  })
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { price: 1000 } }) })
  })

  await page.goto('/')

  // 1. 6 張 .feature-card 全部都是真實 <a> 連結
  const featureLinks = page.locator('a.feature-card')
  await expect(featureLinks).toHaveCount(6)
  for (let i = 0; i < 6; i++) {
    const href = await featureLinks.nth(i).getAttribute('href')
    expect(href).toBeTruthy()
  }

  // 2. 輸入錯字「台基電」按 Enter：留在首頁並顯示友善提示，不導向 /stocks/台基電
  const input = page.locator('.hero-input')
  await input.fill('台基電')
  await input.press('Enter')
  await expect(page.getByTestId('hero-search-error')).toBeVisible()
  await expect(page).toHaveURL(/\/$/)

  // 3. 輸入「台積」顯示即時下拉建議
  await input.fill('台積')
  await expect(page.getByTestId('hero-search-dropdown')).toBeVisible()
  await expect(page.getByTestId('hero-search-dropdown')).toContainText('2330')

  // 4. 回訪交易者（有觀察清單或最近瀏覽）：最近瀏覽＋快捷入口排在宣傳特色區之上
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2330', '2454']))
  })
  await page.reload()
  await expect(page.getByTestId('returning-shortcuts')).toBeVisible()
  const recentBox = await page.getByTestId('recent-panel').boundingBox()
  const featureBox = await page.locator('.feature-section').boundingBox()
  expect(recentBox.y).toBeLessThan(featureBox.y)
})

test('TradeDashboardView：載入中顯示骨架屏不閃現空狀態，且指標數字使用等寬 tabular-nums', async ({ page }) => {
  let releaseApi
  const gate = new Promise((resolve) => { releaseApi = resolve })

  await page.route('**/api/v1/agent/signals*', async (route) => {
    await gate
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [] } }),
    })
  })
  await page.route('**/api/v1/stocks/*/price*', async (route) => {
    await gate
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [] } }),
    })
  })

  await page.goto('/trade-dashboard')

  // 載入中應顯示骨架屏，不閃現「目前沒有價格資料」
  await expect(page.locator('.skeleton-chart')).toBeVisible()
  await expect(page.getByText('目前沒有價格資料')).toHaveCount(0)

  // 驗證金融數字字型為等寬 tabular-nums（非手寫體 Ink Free）
  const metricStyle = await page.locator('.metric-card .value').first().evaluate((el) => {
    const cs = getComputedStyle(el)
    return { fontFamily: cs.fontFamily, numeric: cs.fontVariantNumeric }
  })
  expect(metricStyle.numeric).toContain('tabular-nums')
  expect(metricStyle.fontFamily).not.toMatch(/Ink Free|Segoe Print|Bradley Hand/i)

  // 放行回應後才出現空狀態
  releaseApi()
  await expect(page.getByText('目前沒有價格資料')).toBeVisible()
})
