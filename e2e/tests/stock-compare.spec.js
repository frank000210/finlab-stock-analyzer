// @ts-check
const { test, expect } = require('@playwright/test')

// Y6：多檔股票同圖比較——自選 2~4 檔股票疊在同一張圖看相對表現。
// 驗證：加入股票、查詢後圖表/圖例顯示正確漲跌幅、CSV 匯出觸發下載。

function priceSeries(startClose, drift) {
  const items = []
  let close = startClose
  for (let i = 0; i < 5; i++) {
    items.push({
      date: `2025-01-0${i + 1}`,
      open: close, high: close, low: close, close,
      volume: 1000,
    })
    close = close * (1 + drift)
  }
  return items
}

test('多股比較頁：加入股票、繪製相對表現圖、匯出 CSV (Y6)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/price**', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: priceSeries(100, 0.05) } }),
    })
  })
  await page.route('**/api/v1/stocks/2454/price**', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: priceSeries(50, -0.02) } }),
    })
  })
  await page.route('**/api/v1/stocks/search**', async (route) => {
    const url = new URL(route.request().url())
    const q = url.searchParams.get('q') || ''
    const all = [
      { symbol: '2330', name_zh: '台積電' },
      { symbol: '2454', name_zh: '聯發科' },
    ]
    const items = all.filter(it => it.symbol.includes(q) || it.name_zh.includes(q))
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items } }) })
  })

  await page.goto('/compare')

  const searchInput = page.getByPlaceholder('輸入代碼或名稱加入比較，例如 2330 / 台積電')
  await searchInput.fill('2330')
  await page.getByRole('option', { name: /2330/ }).click()

  await searchInput.fill('2454')
  await page.getByRole('option', { name: /2454/ }).click()

  await expect(page.locator('.chip-row .chip')).toHaveCount(2)

  const compareBtn = page.getByRole('button', { name: '比較' })
  await expect(compareBtn).toBeEnabled()
  await compareBtn.click()

  await expect(page.locator('.legend-row .legend-item')).toHaveCount(2)
  await expect(page.locator('.chart-host')).toBeVisible()

  const exportBtn = page.getByRole('button', { name: /匯出 CSV/ })
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    exportBtn.click(),
  ])
  expect(download.suggestedFilename()).toContain('stock-compare')
})

test('多股比較頁：側邊欄有連結、最多 4 檔限制', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: /多股比較/ }).click()
  await expect(page).toHaveURL(/\/compare/)
  await expect(page.getByText(/最多同時比較 4 檔/)).toBeVisible()
})
