// @ts-check
const { test, expect } = require('@playwright/test')

// A4: 個股行事曆 — 月營收公告、季報期末、除權息歷史，含下次公告的估算。
test('個股行事曆 API 回傳真實歷史事件並標示預估', async ({ request }) => {
  test.setTimeout(120_000)
  const resp = await request.get('/api/v1/analysis/2330/calendar', { timeout: 90_000 })
  expect(resp.ok()).toBeTruthy()
  const data = (await resp.json()).data
  expect(data.events.length).toBeGreaterThan(0)

  // 至少要有一筆真實歷史（非預估）與一筆型別正確標記
  const historical = data.events.filter((e) => !e.estimated)
  expect(historical.length).toBeGreaterThan(0)
  expect(data.events.every((e) => ['revenue', 'financials', 'dividend'].includes(e.type))).toBeTruthy()
  // 事件依日期排序
  const dates = data.events.map((e) => e.date)
  expect([...dates].sort()).toEqual(dates)
})

test('分析頁顯示重要日期卡片', async ({ page }) => {
  await page.goto('/stocks/2330')
  const card = page.locator('.detail-card', { hasText: '重要日期' })
  await expect(card).toBeVisible({ timeout: 60_000 })
  await expect(card).toContainText(/即將到來|近期歷史/)
})
