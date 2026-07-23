// @ts-check
const { test, expect } = require('@playwright/test')

// Y5：CSV 匯出——分析頁(同業比較)/回測頁(交易明細)/類股輪動頁(RRG)/投組風險頁
// (部位表) 原本都完全沒有匯出功能。這裡只驗證按鈕存在、可點擊且觸發下載
// （不驗證檔案內容——jsdom/Playwright 的下載事件足以證明沒有丟出例外）。
//
// DD5：回測頁的策略比較(exportCompareCsv)/參數掃描(exportSweepCsv)匯出已經
// 各自在 backtest-compare.spec.js／backtest-sweep.spec.js 裡測過，這裡只
// 補真正還沒人測的兩個：單一策略模式的交易明細匯出（exportTradesCsv，
// Y5 原始功能）與類股輪動頁的 RRG 匯出（exportRotationCsv）。

test('分析頁 同業比較表有匯出 CSV 按鈕且可觸發下載 (Y5)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/peer-comparison', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', industry: '半導體', group_source: 'industry',
          target: { symbol: '2330', name: '台積電', source: 'target', pe: 20, revenue_yoy_avg: 10, eps: 9, gross_margin: 55, mom20_pct: 1, above_ma200: true },
          peers: [{ symbol: '2454', name: '聯發科', source: 'industry', pe: 18, revenue_yoy_avg: 8, eps: 12, gross_margin: 48, mom20_pct: -1, above_ma200: true }],
        },
      }),
    })
  })

  await page.goto('/stocks/2330')
  const exportBtn = page.getByRole('button', { name: /匯出 CSV/ })
  await expect(exportBtn).toBeVisible({ timeout: 30_000 })
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    exportBtn.click(),
  ])
  expect(download.suggestedFilename()).toContain('peer-comparison')
})

test('投組風險頁 部位表有匯出 CSV 按鈕且可觸發下載 (Y5)', async ({ page }) => {
  await page.goto('/portfolio-heat')
  await page.locator('input[placeholder="代碼 2330"]').fill('2330')
  await page.locator('input[placeholder="進場價"]').fill('900')
  await page.locator('input[placeholder="停損價"]').fill('880')
  await page.locator('input[placeholder="張數"]').fill('1')
  await page.getByRole('button', { name: '加入' }).click()

  const exportBtn = page.getByRole('button', { name: /匯出 CSV/ })
  await expect(exportBtn).toBeVisible({ timeout: 10_000 })
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    exportBtn.click(),
  ])
  expect(download.suggestedFilename()).toContain('portfolio-heat')
})

test('回測頁 單一策略模式交易明細有匯出 CSV 按鈕且可觸發下載 (DD5)', async ({ page }) => {
  await page.goto('/stocks/2330/backtest')
  await page.getByRole('button', { name: '🚀 執行回測' }).click()

  const exportBtn = page.getByRole('button', { name: /匯出 CSV/ })
  await expect(exportBtn).toBeVisible({ timeout: 30_000 })
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    exportBtn.click(),
  ])
  expect(download.suggestedFilename()).toContain('backtest-trades')
})

test('類股輪動頁 RRG 有匯出 CSV 按鈕且可觸發下載 (DD5)', async ({ page }) => {
  await page.goto('/rotation')
  await expect(page.getByRole('heading', { name: 'RRG 輪動時鐘' })).toBeVisible({ timeout: 60_000 })

  const exportBtn = page.getByRole('button', { name: /匯出 CSV/ })
  await expect(exportBtn).toBeVisible({ timeout: 20_000 })
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    exportBtn.click(),
  ])
  expect(download.suggestedFilename()).toContain('rotation-rrg')
})
