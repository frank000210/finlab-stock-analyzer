// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// 官方開放資料倉庫（app/data/open_data.py）：每天把證交所／櫃買／集保的公開資料存進自己的 MongoDB（od_* 集合）。
// 這裡驗 API 契約與權限，不去打任何外部來源（手動觸發時給空的資料集清單，不會發出請求）。
// 解析、日期、被擋停止、冷卻、冪等等邏輯由 backend/tests/test_open_data.py 驗。

const DATASETS = ['attention', 'disposal', 'margin', 'revenue', 'tdcc', 'valuation']
const STATUSES = ['ok', 'partial', 'stale', 'error', 'never']

let h = {}

test.beforeAll(async ({ request }) => {
  h = { 'X-Admin-Token': await getAdminToken(request) }
})

test('健康檢查：公開、不用登入；6 個資料集各有狀態', async ({ request }) => {
  const r = await request.get('/api/v1/open-data/health')
  expect(r.ok()).toBeTruthy()
  const d = (await r.json()).data
  expect(typeof d.ok).toBe('boolean')
  expect(typeof d.cooling_off).toBe('boolean')
  expect(typeof d.running).toBe('boolean')
  expect(Object.keys(d.datasets).sort()).toEqual(DATASETS)
  for (const k of DATASETS) {
    expect(STATUSES).toContain(d.datasets[k].status)
    expect(d.datasets[k].label).toBeTruthy()
  }
  expect(Array.isArray(d.stale)).toBeTruthy()
})

test('狀態與手動觸發要管理員 token（沒帶回 401）', async ({ request }) => {
  expect((await request.get('/api/v1/open-data/status')).status()).toBe(401)
  expect((await request.post('/api/v1/open-data/run', { data: {} })).status()).toBe(401)
})

test('狀態：各集合筆數、各來源結果、最近幾輪', async ({ request }) => {
  const r = await request.get('/api/v1/open-data/status', { headers: h })
  expect(r.ok()).toBeTruthy()
  const d = (await r.json()).data
  expect(Object.keys(d.stored_counts).sort()).toEqual(DATASETS)
  for (const k of DATASETS) expect(typeof d.stored_counts[k]).toBe('number')
  expect(Array.isArray(d.recent_runs)).toBeTruthy()
  expect(d.sources).toBeDefined()
})

test('手動觸發：未知資料集回 400；空清單的一輪不發出任何請求、只留紀錄', async ({ request }) => {
  const bad = await request.post('/api/v1/open-data/run', { headers: h, data: { datasets: ['nope'] } })
  expect(bad.status()).toBe(400)

  // 啟動後的補跑可能正在執行：等它結束再觸發
  let started = false
  await expect.poll(async () => {
    const r = await request.post('/api/v1/open-data/run', { headers: h, data: { datasets: [] } })
    started = (await r.json()).data.started
    return started
  }, { timeout: 120_000, intervals: [2_000] }).toBeTruthy()

  await expect.poll(async () => {
    const d = (await (await request.get('/api/v1/open-data/status', { headers: h })).json()).data
    if (d.cooling_off) return 'cooling' // 先前被來源擋過：這輪會被略過、不留紀錄，也算正常
    const mine = d.recent_runs.find((x) => x.trigger === 'manual' && x.datasets.length === 0)
    return !d.running && mine ? 'done' : ''
  }, { timeout: 60_000 }).toMatch(/done|cooling/)
})

test('讀已存資料：唯讀、不用登入；壞參數被擋；沒存過的股票回空清單', async ({ request }) => {
  expect((await request.get('/api/v1/open-data/data/nope/2330')).status()).toBe(400)
  expect((await request.get('/api/v1/open-data/data/margin/bad%20symbol!')).status()).toBe(400)
  expect((await request.get('/api/v1/open-data/data/margin/2330?start=2026/01/01')).status()).toBe(422)
  expect((await request.get('/api/v1/open-data/data/margin/2330?limit=0')).status()).toBe(422)
  expect((await request.get('/api/v1/open-data/data/margin/2330?limit=1001')).status()).toBe(422)

  const r = await request.get('/api/v1/open-data/data/margin/9999?limit=5')
  expect(r.ok()).toBeTruthy()
  const d = (await r.json()).data
  expect(d.dataset).toBe('margin')
  expect(d.symbol).toBe('9999')
  expect(d.count).toBe(0)
  expect(d.rows).toEqual([])

  // 月營收的日期欄位是 ym（YYYY-MM），也接受只到月份的區間
  const rev = await request.get('/api/v1/open-data/data/revenue/2330?start=2026-01&end=2026-12&limit=3')
  expect(rev.ok()).toBeTruthy()
  const rows = (await rev.json()).data.rows
  expect(Array.isArray(rows)).toBeTruthy()
  const yms = rows.map((x) => x.ym)
  expect(yms).toEqual([...yms].sort()) // 由舊到新
})
