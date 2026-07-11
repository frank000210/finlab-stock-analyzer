// @ts-check
const { test, expect } = require('@playwright/test')

// F7: 交易儀表板接真實資料 — 「投資組合價值」原本是寫死的 5,000,000 常數，
// 「風險總覽」則是打 backend risk_manager 的模擬亂數權益曲線。現在兩者都
// 改用「交易日誌」(finlab_trade_journal) 的已平倉紀錄計算：帳戶資金＋實際
// 已實現損益、實際回撤(MDD)、實際當日交易數與熔斷狀態。
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/agent/signals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { items: [{ id: 's1', symbol: '2330', type: 'BUY', confidence: 0.8, reasoning: '測試訊號' }] },
      }),
    })
  })
  await page.route('**/api/v1/stocks/2330/price*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330',
          period: '1d',
          items: [
            { date: '2026-07-09', open: 600, high: 605, low: 595, close: 600, volume: 1000 },
            { date: '2026-07-10', open: 600, high: 610, low: 598, close: 605, volume: 1200 },
          ],
          source: 'test',
          as_of: '2026-07-10',
        },
      }),
    })
  })
})

test('交易儀表板 尚無交易日誌紀錄時顯示帳戶起始資金與 ACTIVE (F7)', async ({ page }) => {
  await page.goto('/trade-dashboard')
  await page.evaluate(() => {
    localStorage.removeItem('finlab_trade_journal')
    localStorage.removeItem('portfolio_heat_account')
  })
  await page.reload()

  const expected = await page.evaluate(() => new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 }).format(1000000))
  const card = page.locator('.metric-card').first()
  await expect(card).toContainText(`NT$ ${expected}`)
  await expect(card).toContainText('帳戶起始資金')
  await expect(page.locator('.risk-grid')).toContainText('ACTIVE')
  await expect(page.locator('.risk-grid')).toContainText('0.00%')
})

test('交易儀表板 依交易日誌已實現損益計算投組價值與熔斷狀態 (F7)', async ({ page }) => {
  const journal = [{
    id: 'd1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 6, tag: '', openDate: '2026-07-01', status: 'closed', exit: 90, exitDate: '2026-07-01',
  }]
  await page.goto('/trade-dashboard')
  await page.evaluate((j) => {
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_trade_journal', JSON.stringify(j))
  }, journal)
  await page.reload()

  // 1,000,000 - 60,000 = 940,000；回撤 60,000/1,000,000 = 6.00% -> WARNING
  const expected = await page.evaluate(() => new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 }).format(940000))
  const card = page.locator('.metric-card').first()
  await expect(card).toContainText(`NT$ ${expected}`)
  await expect(card).toContainText('交易日誌已實現損益')
  await expect(page.locator('.risk-grid')).toContainText('WARNING')
  await expect(page.locator('.risk-grid')).toContainText('6.00%')
})
