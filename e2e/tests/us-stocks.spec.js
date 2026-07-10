// @ts-check
const { test, expect } = require('@playwright/test')

// 美股指數與龍頭股支援：yfinance 直查、內建中文名、全鏈可用。
test('美股價格 API：AAPL 與 ^GSPC 回真實資料', async ({ request }) => {
  test.setTimeout(120_000)

  const aapl = await request.get('/api/v1/stocks/AAPL/price?start=2026-06-01&end=2026-07-10', { timeout: 90_000 })
  expect(aapl.ok()).toBeTruthy()
  const aaplData = (await aapl.json()).data
  expect(aaplData.items.length).toBeGreaterThan(10)
  expect(aaplData.source).toBe('yfinance')

  const spx = await request.get(`/api/v1/stocks/${encodeURIComponent('^GSPC')}/price?start=2026-06-01&end=2026-07-10`, { timeout: 90_000 })
  expect(spx.ok()).toBeTruthy()
  expect(((await spx.json()).data.items || []).length).toBeGreaterThan(10)
})

test('美股 info 與搜尋帶中文名', async ({ request }) => {
  const info = await request.get('/api/v1/stocks/NVDA/info')
  expect((await info.json()).data.name_zh).toBe('輝達')

  const search = await request.get('/api/v1/stocks/search?q=NVDA')
  const items = (await search.json()).data.items
  expect(items.some((i) => i.symbol === 'NVDA' && i.name_zh === '輝達')).toBeTruthy()
})

test('美股可算部位風控（ATR 停損）', async ({ request }) => {
  test.setTimeout(120_000)
  const resp = await request.get('/api/v1/risk/sizing/AAPL', { timeout: 90_000 })
  expect(resp.ok()).toBeTruthy()
  const data = (await resp.json()).data
  expect(data.name).toBe('蘋果')
  expect(data.atr).toBeGreaterThan(0)
  expect(data.suggested_stops.length).toBe(3)
})

test('Ctrl+K 搜美股龍頭並跳分析頁', async ({ page }) => {
  await page.goto('/journal')
  await page.keyboard.press('Control+k')
  await page.locator('.qs-input').fill('NVDA')

  const hit = page.locator('.qs-item', { hasText: '輝達' })
  await expect(hit).toBeVisible({ timeout: 20_000 })
  await hit.click()
  await expect(page).toHaveURL(/\/stocks\/NVDA/)
})
