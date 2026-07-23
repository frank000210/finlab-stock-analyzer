// @ts-check
const { test, expect } = require('@playwright/test')

// Y1：觀察清單管理頁面。整合原本散落在 DecisionView/GraphView/Graph01View/
// RotationView 的重複邏輯成單一事實來源，並修正 GraphView/RotationView
// 原本會用「這次要畫圖的組合」覆蓋掉共用觀察清單的問題。

test('觀察清單頁 新增/移除/排序，且與作戰台等頁面共用同一份清單 (Y1)', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: '2317', name_zh: '鴻海' }] } }),
    })
  })

  await page.goto('/watchlist')
  await page.evaluate(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['2330'])))
  await page.reload()

  await expect(page.getByRole('heading', { name: /觀察清單（1 檔）/ })).toBeVisible({ timeout: 20_000 })
  await expect(page.locator('.symbol-link', { hasText: '2330' })).toBeVisible()

  // 新增
  const input = page.locator('.search-shell input')
  await input.fill('2317')
  await page.getByRole('option', { name: /2317/ }).click()
  await expect(page.getByRole('heading', { name: /觀察清單（2 檔）/ })).toBeVisible({ timeout: 10_000 })

  // 確認寫回 localStorage 是共用 key，供 DecisionView 等頁面讀取
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist') || '[]'))
  expect(stored).toContain('2330')
  expect(stored).toContain('2317')

  // 移除（DD6：現在會跳確認對話框，預設接受）
  page.once('dialog', (d) => d.accept())
  const row = page.locator('tr', { hasText: '2330' })
  await row.getByRole('button', { name: /移除/ }).click()
  await expect(page.getByRole('heading', { name: /觀察清單（1 檔）/ })).toBeVisible()
  const afterRemove = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist') || '[]'))
  expect(afterRemove).not.toContain('2330')
})

test('GraphView 套用自訂股票組合不會覆蓋共用觀察清單 (Y1 bug fix)', async ({ page }) => {
  await page.goto('/graph')
  await page.evaluate(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['2330', '2317', '2454'])))
  await page.evaluate(() => localStorage.removeItem('finlab_graph_symbols'))
  await page.reload()

  // 在 GraphView 輸入完全不同的股票組合並套用
  const symbolInput = page.locator('input[placeholder="2330,2317,2454"]')
  await expect(symbolInput).toBeVisible({ timeout: 20_000 })
  await symbolInput.fill('9999,8888')
  await page.getByRole('button', { name: '套用觀察池' }).click()

  // 修正前：套用會把 finlab_watchlist 也覆寫成 9999,8888；修正後：共用觀察
  // 清單必須維持原樣，只有本頁專屬的 finlab_graph_symbols 被更新
  const watchlistAfter = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist') || '[]'))
  expect(watchlistAfter).toEqual(['2330', '2317', '2454'])
})
