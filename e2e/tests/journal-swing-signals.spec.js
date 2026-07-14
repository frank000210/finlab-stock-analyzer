// @ts-check
const { test, expect } = require('@playwright/test')

// N1-N4：波段留倉信號（NotebookLM「Humbled Trader」頻道的當沖規則波段化調整）
// 這幾個訊號都是「當沖不用管、波段留倉才要管」的東西：地雷日、未實現獲利
// 回吐、8EMA 趨勢轉弱，以及進場前的 200 日均線濾網。

test('交易日誌 進行中部位 未實現獲利回吐超過門檻時顯示警示 (N2)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', name: '台積電', industry: '半導體業', price: 142, atr: 5, atr_period: 14, atr_pct: 3.5,
          suggested_stops: [{ label: '穩健', mult: 2, stop_price: 132, distance: 10, distance_pct: 7 }],
          as_of: '2026-07-11', source: 'finmind',
        },
      }),
    })
  })
  await page.route('**/api/v1/stocks/2330/price', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2330', period: '1d', items: [], source: 'finmind', as_of: null } }),
    })
  })
  await page.route('**/api/v1/analysis/2330/calendar', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { symbol: '2330', events: [], as_of: '2026-07-11' } }) })
  })

  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    // 進場100，現價142 -> 未實現損益 = (142-100)*1000 = 42,000；峰值曾到 70,000
    // -> 回吐 (70000-42000)/70000 = 40%，超過 30% 門檻應該顯示警示。
    { id: 'n2-1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null, lots: 1, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null, peakUnrealizedPnl: 70000 },
  ])))
  await page.reload()

  const row = page.locator('.j-table tbody tr', { hasText: '2330' })
  await expect(row).toContainText('142.00', { timeout: 20_000 })
  await expect(row.locator('.giveback-tag')).toBeVisible()
  await expect(row.locator('.giveback-tag')).toContainText('回吐40%')
})

test('交易日誌 進行中部位 日K收盤跌破8日均線時顯示趨勢轉弱警示 (N4)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { symbol: '2330', name: '台積電', industry: '半導體業', price: 80, atr: 5, atr_period: 14, atr_pct: 6.25, suggested_stops: [], as_of: '2026-07-11', source: 'finmind' },
      }),
    })
  })
  // 前 8 天緩步上漲、第 10 天（最新一根）大跌，EMA8 還沒跟上，最新收盤跌破 EMA8。
  const closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 80]
  await page.route('**/api/v1/stocks/2330/price', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', period: '1d',
          items: closes.map((c, i) => ({ date: `2026-06-${(i + 1).toString().padStart(2, '0')}`, open: c, high: c, low: c, close: c, volume: 1000 })),
          source: 'finmind', as_of: '2026-06-10',
        },
      }),
    })
  })
  await page.route('**/api/v1/analysis/2330/calendar', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { symbol: '2330', events: [], as_of: '2026-07-11' } }) })
  })

  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    // 停損設在 70（低於現價 80），確保這裡測的是「跌破 8EMA」而不是「觸及停損」
    // ——兩個警示互斥（v-else-if），停損優先顯示，要避開才能測到 EMA 那個。
    { id: 'n4-1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 70, target: null, lots: 1, tag: '', openDate: '2026-06-01', status: 'open', exit: null, exitDate: null },
  ])))
  await page.reload()

  const row = page.locator('.j-table tbody tr', { hasText: '2330' })
  await expect(row).toContainText('80.00', { timeout: 20_000 })
  await expect(row.locator('.ema-tag')).toBeVisible()
  await expect(row.locator('.ema-tag')).toContainText('跌破8EMA')
})

test('交易日誌 進行中部位 7天內有財報等行事曆事件時顯示地雷日警示 (N1)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { symbol: '2330', name: '台積電', industry: '半導體業', price: 100, atr: 5, atr_period: 14, atr_pct: 5, suggested_stops: [], as_of: '2026-07-11', source: 'finmind' },
      }),
    })
  })
  await page.route('**/api/v1/stocks/2330/price', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { symbol: '2330', period: '1d', items: [], source: 'finmind', as_of: null } }) })
  })
  await page.route('**/api/v1/analysis/2330/calendar', async (route) => {
    const soon = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10)
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2330', events: [{ date: soon, type: 'financials', label: '下次財報法定公告截止日（預估）', estimated: true, detail: '' }], as_of: '2026-07-11' } }),
    })
  })

  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    { id: 'n1-1', symbol: '2330', name: '台積電', side: 'long', entry: 90, stop: 80, target: null, lots: 1, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null },
  ])))
  await page.reload()

  const row = page.locator('.j-table tbody tr', { hasText: '2330' })
  await expect(row.locator('.event-tag')).toBeVisible({ timeout: 20_000 })
})

test('部位風控 波段濾網顯示個股是否站上200日均線 (N3)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', name: '台積電', industry: '半導體業', price: 142, atr: 5, atr_period: 14, atr_pct: 3.5,
          suggested_stops: [{ label: '穩健', mult: 2, stop_price: 132, distance: 10, distance_pct: 7 }],
          setup: { total: 60, verdict: '普通', target: 150, rr: 1.5, components: [] },
          ma200: 120, above_ma200: true, ma200_rising: true,
          as_of: '2026-07-11', source: 'finmind',
        },
      }),
    })
  })
  await page.goto('/risk-sizing')
  await page.locator('.symbol-box input').fill('2330')
  await page.getByRole('button', { name: '查詢' }).click()

  await expect(page.locator('.ma200-badge.good').first()).toContainText('站上年線')
  await expect(page.locator('.ma200-badge').filter({ hasText: '年線上揚' })).toBeVisible()
})
