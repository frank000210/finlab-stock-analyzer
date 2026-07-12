// @ts-check
const { test, expect } = require('@playwright/test')

// D1 TradingView 嵌入：分析頁可切換官方 Advanced Chart widget（指標/畫線齊
// 全、不耗 FinMind 額度），內建 lightweight-charts 仍是預設（離線可用、資料
// 餵得進自家計算管線）。測試把 tradingview.com 外部資源擋掉，只驗證切換行為
// 與容器掛載，不依賴外部網路。
test.beforeEach(async ({ page }) => {
  await page.route('**://*.tradingview.com/**', (route) => route.abort())
})

test('分析頁 預設內建圖表，可切換 TradingView 並記住偏好 (D1)', async ({ page }) => {
  await page.goto('/stocks/2330')
  await page.evaluate(() => localStorage.removeItem('finlab_chart_mode'))
  await page.reload()

  // 預設：內建圖表模式，chart-stack 顯示、TV 容器不存在
  await expect(page.locator('.chart-mode-toggle .range-button', { hasText: '內建圖表' })).toHaveClass(/active/)
  await expect(page.locator('.chart-stack')).toBeVisible()
  await expect(page.locator('.tv-host')).toHaveCount(0)

  // 外連連結指向 TradingView，台股掛 TWSE 前綴
  const href = await page.locator('.tv-link').first().getAttribute('href')
  expect(href).toContain('tradingview.com/chart/?symbol=TWSE%3A2330')

  // 切到 TradingView：容器掛載、內建圖表堆疊隱藏、時間框架選單收起
  await page.locator('.chart-mode-toggle .range-button', { hasText: 'TradingView' }).click()
  await expect(page.locator('.tv-host')).toBeVisible()
  await expect(page.locator('.chart-stack')).toBeHidden()
  await expect(page.locator('.range-selector')).toBeHidden()

  // 偏好持久化：重新整理後仍是 TradingView 模式
  await page.reload()
  await expect(page.locator('.chart-mode-toggle .range-button', { hasText: 'TradingView' })).toHaveClass(/active/)
  await expect(page.locator('.tv-host')).toBeVisible()

  // 切回內建：圖表恢復顯示
  await page.locator('.chart-mode-toggle .range-button', { hasText: '內建圖表' }).click()
  await expect(page.locator('.chart-stack')).toBeVisible()
  await expect(page.locator('.tv-host')).toHaveCount(0)
})
