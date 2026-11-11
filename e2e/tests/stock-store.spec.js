// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// 每日資料庫：白名單股票的資料增量存進 MongoDB（app/data/stock_store.py）。
// 這裡驗 API 契約與白名單規則；不打 FinMind（白名單設成空清單再觸發，沒有要抓的股票）。
// 增量起點、upsert 不重複、額度用完停止等邏輯由 backend/tests/test_stock_store.py 驗。

let h = {}
let original = []

test.beforeAll(async ({ request }) => {
  h = { 'X-Admin-Token': await getAdminToken(request) }
  const r = await request.get('/api/v1/store/whitelist', { headers: h })
  original = (await r.json()).data.symbols
})

test.afterAll(async ({ request }) => {
  await request.put('/api/v1/store/whitelist', { headers: h, data: { symbols: original } })
})

test('白名單：存檔會轉大寫、去重、保持順序；讀回來一致', async ({ request }) => {
  const put = await request.put('/api/v1/store/whitelist', { headers: h, data: { symbols: ['2330', ' 0050 ', '2330', '00940b'] } })
  expect(put.ok()).toBeTruthy()
  expect((await put.json()).data.symbols).toEqual(['2330', '0050', '00940B'])

  const get = await request.get('/api/v1/store/whitelist', { headers: h })
  const d = (await get.json()).data
  expect(d.symbols).toEqual(['2330', '0050', '00940B'])
  expect(d.source).toBe('db')
  expect(d.max_symbols).toBe(100)
})

test('白名單：格式不對、超過 100 檔都被擋（400）；沒帶管理員 token 回 401', async ({ request }) => {
  const bad = await request.put('/api/v1/store/whitelist', { headers: h, data: { symbols: ['2330', '23'] } })
  expect(bad.status()).toBe(400)
  const many = Array.from({ length: 101 }, (_, i) => String(1000 + i))
  const tooMany = await request.put('/api/v1/store/whitelist', { headers: h, data: { symbols: many } })
  expect(tooMany.status()).toBe(400)

  expect((await request.get('/api/v1/store/whitelist')).status()).toBe(401)
  expect((await request.put('/api/v1/store/whitelist', { data: { symbols: ['2330'] } })).status()).toBe(401)
  expect((await request.post('/api/v1/store/run', { data: {} })).status()).toBe(401)
})

test('狀態：列出白名單、5 個資料集、各集合筆數與最近幾輪', async ({ request }) => {
  await request.put('/api/v1/store/whitelist', { headers: h, data: { symbols: ['2330'] } })
  const r = await request.get('/api/v1/store/status', { headers: h })
  expect(r.ok()).toBeTruthy()
  const d = (await r.json()).data
  expect(d.whitelist.symbols).toEqual(['2330'])
  expect(Object.keys(d.datasets).sort()).toEqual(['institutional', 'margin', 'price', 'revenue', 'valuation'])
  for (const k of Object.keys(d.datasets)) expect(typeof d.stored_counts[k]).toBe('number')
  expect(Array.isArray(d.recent_runs)).toBeTruthy()
  expect(d.symbols['2330']).toBeDefined()
})

test('手動觸發：背景執行並留下紀錄；未知資料集與壞代號回 400', async ({ request }) => {
  expect((await request.post('/api/v1/store/run', { headers: h, data: { datasets: ['nope'] } })).status()).toBe(400)
  expect((await request.post('/api/v1/store/run', { headers: h, data: { symbols: ['x'] } })).status()).toBe(400)

  // 指定空的股票清單：不會打 FinMind，只留下一筆「白名單是空的」的紀錄
  const start = await request.post('/api/v1/store/run', { headers: h, data: { symbols: [] } })
  expect(start.ok()).toBeTruthy()

  await expect.poll(async () => {
    const d = (await (await request.get('/api/v1/store/status', { headers: h })).json()).data
    return !d.running && d.recent_runs.length > 0 && d.recent_runs[0].trigger === 'manual' && d.recent_runs[0].symbols === 0
  }, { timeout: 30_000 }).toBeTruthy()

  const last = (await (await request.get('/api/v1/store/status', { headers: h })).json()).data.recent_runs[0]
  expect(last.rows).toBe(0)
  expect(last.aborted).toBeNull()
  expect(last.note).toContain('白名單')
})

test('讀已存資料：唯讀、不用登入；未知資料集 400、沒存過的股票回空清單', async ({ request }) => {
  expect((await request.get('/api/v1/store/data/nope/2330')).status()).toBe(400)
  expect((await request.get('/api/v1/store/data/price/zz')).status()).toBe(400)
  const r = await request.get('/api/v1/store/data/price/9999?limit=5')
  expect(r.ok()).toBeTruthy()
  const d = (await r.json()).data
  expect(d.dataset).toBe('price')
  expect(d.symbol).toBe('9999')
  expect(Array.isArray(d.rows)).toBeTruthy()
})
