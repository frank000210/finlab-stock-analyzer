// @ts-check
const { test, expect } = require('@playwright/test')

// W6+W7：AI 複盤（找規則式教練沒設計到的細緻模式）＋進場理由品質檢查。
// 交易日誌全在 localStorage，種 15 筆已平倉交易讓 AI 複盤按鈕滿足門檻
// （少於 10 筆後端會拒絕分析）。

function makeClosedTrades(n) {
  const out = []
  for (let i = 0; i < n; i++) {
    out.push({
      id: `t${i}`, symbol: '2330', name: '台積電', side: 'long',
      entry: 900, stop: 880, target: 950, lots: 1,
      tag: i % 2 ? '突破' : '拉回', catalyst: i % 3 === 0 ? '財報優於預期' : '',
      openDate: '2026-06-01', status: 'closed',
      exit: i % 3 === 0 ? 880 : 920, exitDate: '2026-06-05',
    })
  }
  return out
}

test('交易日誌 AI 複盤按鈕滿足門檻後可觸發並顯示細緻模式分析 (W6)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  let called = 0
  await page.route('**/api/v1/journal/ai-coach', async (route) => {
    called += 1
    const body = route.request().postDataJSON()
    expect(body.trades.length).toBeGreaterThanOrEqual(10)
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { insight: '「財報優於預期」理由的交易全數虧損，建議檢視進場時機。' } }),
    })
  })

  await page.goto('/journal')
  await page.evaluate((trades) => localStorage.setItem('finlab_trade_journal', JSON.stringify(trades)), makeClosedTrades(15))
  await page.reload()

  const coachSection = page.locator('.section-block', { hasText: '複盤教練' })
  await expect(coachSection).toBeVisible({ timeout: 30_000 })
  const aiBtn = coachSection.getByRole('button', { name: /AI 複盤/ })
  await expect(aiBtn).toBeVisible()
  await aiBtn.click()

  await expect(coachSection.locator('.ai-coach-box')).toBeVisible({ timeout: 30_000 })
  expect(called).toBe(1)
  await expect(coachSection.locator('.ai-coach-box')).toContainText('財報優於預期')
})

test('交易日誌 進場理由品質檢查按鈕回傳評語 (W7)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  await page.route('**/api/v1/journal/catalyst-quality', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.catalyst).toBe('感覺會漲')
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { assessment: '空泛。建議加入具體依據。' } }),
    })
  })

  await page.goto('/journal')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  await page.locator('.add-form input[placeholder="代碼 2330"]').fill('2330')
  await page.locator('.add-form input[placeholder="進場價"]').fill('900')
  await page.locator('.add-form input[placeholder="停損價"]').fill('880')
  await page.locator('.add-form input[placeholder="張數"]').fill('1')
  await page.locator('.add-form input[placeholder="進場理由/催化劑(選填)"]').fill('感覺會漲')

  await page.getByRole('button', { name: '檢查理由品質' }).click()
  await expect(page.getByText('空泛。建議加入具體依據')).toBeVisible({ timeout: 30_000 })
})
