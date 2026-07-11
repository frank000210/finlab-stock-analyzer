// @ts-check
const { test, expect } = require('@playwright/test')

// C10: price alerts — set a per-symbol threshold, scheduler checks in the
// background and pushes a Telegram notification once when it's breached.
test('C10 價格警報 API：新增/列表/刪除', async ({ request }) => {
  const create = await request.post('/api/v1/risk/alerts', {
    data: { symbol: '2330', direction: 'above', target_price: 999999, note: '測試' },
  })
  expect(create.ok()).toBeTruthy()
  const alert = (await create.json()).data
  expect(alert.symbol).toBe('2330')
  expect(alert.triggered).toBe(false)
  expect(alert.active).toBe(true)

  const list = await request.get('/api/v1/risk/alerts')
  expect(list.ok()).toBeTruthy()
  const items = (await list.json()).data.items
  expect(items.some(a => a.id === alert.id)).toBeTruthy()

  const del = await request.delete(`/api/v1/risk/alerts/${alert.id}`)
  expect(del.ok()).toBeTruthy()

  const list2 = await request.get('/api/v1/risk/alerts')
  const items2 = (await list2.json()).data.items
  expect(items2.some(a => a.id === alert.id)).toBeFalsy()
})

test('C10 價格警報 API：立即檢查回傳 checked/triggered 統計', async ({ request }) => {
  test.setTimeout(120_000)
  const create = await request.post('/api/v1/risk/alerts', {
    data: { symbol: '2330', direction: 'above', target_price: 999999 },
  })
  const alert = (await create.json()).data
  const check = await request.post('/api/v1/risk/alerts/check', { timeout: 90_000 })
  expect(check.ok()).toBeTruthy()
  const data = (await check.json()).data
  expect(data.checked).toBeGreaterThanOrEqual(1)
  expect(data.triggered).toBe(0) // 目標價 999999 現價不可能觸發
  await request.delete(`/api/v1/risk/alerts/${alert.id}`)
})

test('價格警報頁：新增顯示於清單並可刪除', async ({ page }) => {
  // Mongo-backed, not localStorage — clear any leftover alerts from prior runs first.
  const existing = await page.request.get('/api/v1/risk/alerts')
  for (const a of (await existing.json()).data.items) {
    await page.request.delete(`/api/v1/risk/alerts/${a.id}`)
  }

  await page.goto('/price-alerts')
  await expect(page.getByRole('heading', { name: /新增價格警報/ })).toBeVisible()

  await page.getByPlaceholder('代碼 2330').fill('2454')
  await page.getByPlaceholder('目標價').fill('9999')
  await page.getByPlaceholder('備註（選填）').fill('e2e測試')
  await page.getByRole('button', { name: '加入' }).click()

  await expect(page.locator('.alert-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.alert-table')).toContainText('2454')
  await expect(page.locator('.alert-table')).toContainText('9,999.00')
  await expect(page.locator('.alert-table')).toContainText('監控中')

  await page.locator('.alert-table .del').click()
  await expect(page.locator('.alert-table tbody tr')).toHaveCount(0)
})
