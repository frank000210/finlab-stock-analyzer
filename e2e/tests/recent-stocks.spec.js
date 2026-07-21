// @ts-check
const { test, expect } = require('@playwright/test')

// Y4：最近瀏覽股票原本永遠顯示假占位文字「等待同步報價」（saveRecent 從
// 未存過價格），且沒有刪除單筆/清空的功能。

test('首頁 最近瀏覽股票顯示真實報價並可個別移除/清空 (Y4)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { price: 1050 } }) })
  })

  await page.goto('/')
  await page.evaluate(() => {
    localStorage.setItem('recentStocks', JSON.stringify([
      { symbol: '2330', name: '台積電' },
      { symbol: '2317', name: '鴻海' },
    ]))
  })
  await page.reload()

  const cards = page.locator('.recent-card-wrap')
  await expect(cards).toHaveCount(2, { timeout: 20_000 })

  // 修正前：不管抓不抓得到報價都永遠顯示「等待同步報價」；修正後：查得到
  // 就顯示真實價格，不再是恆假的占位文字
  await expect(cards.first()).not.toContainText('等待同步報價', { timeout: 10_000 })
  await expect(cards.first()).toContainText('1,050')

  // 移除單筆
  await page.locator('.recent-remove').first().click()
  await expect(cards).toHaveCount(1)
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('recentStocks') || '[]'))
  expect(stored.length).toBe(1)

  // 清空
  page.on('dialog', d => d.accept())
  await page.getByRole('button', { name: '清空' }).click()
  await expect(page.getByText('尚無最近瀏覽紀錄')).toBeVisible()
  const storedAfterClear = await page.evaluate(() => localStorage.getItem('recentStocks'))
  expect(storedAfterClear).toBeNull()
})
