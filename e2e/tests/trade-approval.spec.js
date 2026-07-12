// @ts-check
const { test, expect } = require('@playwright/test')

// C1 交易核准中心接真實流程：過去「核准」只翻後端記憶體裡的狀態旗標，核准
// 之後什麼都不會發生（也沒有任何測試覆蓋）。現在核准即寫入交易日誌成為紙上
// 交易（停損比照「穩健」2×ATR 慣例），與作戰台「記錄」走同一條路，之後平倉
// 就進 R 值統計、也被風控監控的真實回撤/熔斷看到。
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/trade/pending*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          items: [{
            task_id: 't1', symbol: '2330', type: 'BUY', confidence: 0.85, quantity: 2000,
            estimated_price: 100, reasoning: '測試提案', created_at: '2026-07-11T09:00:00',
            status: 'PENDING', is_simulated: true,
          }],
        },
      }),
    })
  })
  await page.route('**/api/v1/trade/approve', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { task_id: 't1', status: 'APPROVED' } }),
    })
  })
  await page.route('**/api/v1/risk/sizing/2330*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2330', name: '台積電', price: 100, atr: 2.5, suggested_stops: [], setup: null } }),
    })
  })
})

test('交易核准中心 核准後寫入交易日誌成為紙上交易 (C1)', async ({ page }) => {
  await page.goto('/trade-approval')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  await expect(page.locator('.trade-card')).toHaveCount(1)
  await page.getByRole('button', { name: '核准' }).click()

  await expect(page.locator('.log-msg')).toContainText('已核准 2330 並記錄到交易日誌')
  await expect(page.locator('.log-msg')).toContainText('停損 95') // 100 − 2×ATR(2.5)

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal).toHaveLength(1)
  expect(journal[0]).toMatchObject({
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 95, lots: 2, status: 'open', tag: 'AI核准',
  })
})

test('交易核准中心 同代碼已有進行中部位時不重複寫入 (C1)', async ({ page }) => {
  await page.goto('/trade-approval')
  await page.evaluate(() => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify([{
      id: 'x1', symbol: '2330', name: '台積電', side: 'long', entry: 98, stop: 92, target: null,
      lots: 1, tag: '', openDate: '2026-07-10', status: 'open', exit: null, exitDate: null,
    }]))
  })
  await page.reload()

  await page.getByRole('button', { name: '核准' }).click()
  await expect(page.locator('.log-msg')).toContainText('未重複寫入')

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal).toHaveLength(1)
  expect(journal[0].entry).toBe(98)
})
