// @ts-check
const { test, expect } = require('@playwright/test')

// Left sidebar: collapsible, houses the global stock search that drives
// every page's default symbol + live content sync.

test('側欄可收合並持久保存狀態', async ({ page }) => {
  await page.goto('/')
  const sidebar = page.locator('.app-sidebar')
  await expect(sidebar).toBeVisible()
  await expect(sidebar).not.toHaveClass(/collapsed/)

  await page.locator('.collapse-btn').click()
  await expect(sidebar).toHaveClass(/collapsed/)

  await page.reload()
  await expect(page.locator('.app-sidebar')).toHaveClass(/collapsed/) // persisted

  // restore for other tests in this worker
  await page.locator('.collapse-btn').click()
  await expect(page.locator('.app-sidebar')).not.toHaveClass(/collapsed/)
})

test('側欄搜尋切換個股：在分析子頁時保留子頁、換代號、內容連動', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: 'AAPL', name_zh: '蘋果', market: 'us', industry: '科技' }] } }),
    })
  })

  await page.goto('/stocks/2330/seasonal')
  await expect(page.locator('h1', { hasText: '季節性分析' })).toBeVisible()

  await page.locator('.sidebar-search-input').fill('AAPL')
  const hit = page.locator('.sidebar-search-dropdown li', { hasText: '蘋果' })
  await expect(hit).toBeVisible()
  await hit.click()

  // 保留在季節性子頁，只是代號換成 AAPL
  await expect(page).toHaveURL(/\/stocks\/AAPL\/seasonal/)

  // 目前個股卡片也同步顯示
  await expect(page.locator('.sidebar-current')).toContainText('AAPL')
})

test('側欄搜尋更新部位風控頁的預設代號輸入欄位', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: 'NVDA', name_zh: '輝達', market: 'us', industry: '半導體' }] } }),
    })
  })
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: 'NVDA', name: '輝達', industry: '半導體', price: 200, atr: 6, atr_period: 14, atr_pct: 3,
          suggested_stops: [{ label: '穩健', mult: 2, stop_price: 188, distance: 12, distance_pct: 6 }],
          as_of: '2026-07-10', source: 'yfinance',
        },
      }),
    })
  })

  await page.goto('/risk-sizing') // 沒有路由代號的工具頁
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 30_000 })

  await page.locator('.sidebar-search-input').fill('NVDA')
  const hit = page.locator('.sidebar-search-dropdown li', { hasText: '輝達' })
  await expect(hit).toBeVisible()
  await hit.click()

  // 停在原頁，但代號輸入欄位以 NVDA 為預設值、資料連動重新載入
  await expect(page).toHaveURL(/\/risk-sizing/)
  await expect(page.locator('.symbol-box input')).toHaveValue('NVDA')
  await expect(page.locator('.mval').first()).toContainText('200')
})
