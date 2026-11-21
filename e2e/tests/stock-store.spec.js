// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// 每日資料庫：白名單股票的資料增量存進 MongoDB（app/data/stock_store.py）。
// 這裡驗 API 契約與白名單規則；不打 FinMind（白名單設成空清單再觸發，沒有要抓的股票）。
// 增量起點、upsert 不重複、額度用完停止等邏輯由 backend/tests/test_stock_store.py 驗。

let h = {}
let adminToken = ''
let original = []

test.beforeAll(async ({ request }) => {
  adminToken = await getAdminToken(request)
  h = { 'X-Admin-Token': adminToken }
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

// ───────────────────── 後台管理頁：每日資料庫白名單與同步狀態 UI ─────────────────────

async function seedRealAdminSession(page, token) {
  await page.addInitScript((tok) => {
    localStorage.setItem('admin_token', tok)
    localStorage.setItem('admin_user', JSON.stringify({
      email: 'admin@finlab.local', name: 'Admin', avatar: '', is_admin: true,
    }))
    try { localStorage.setItem('finlab_onboarded', '1') } catch { /* ignore */ }
  }, token)
}

function attachErrorWatchers(page) {
  const pageErrors = []
  const consoleErrors = []
  page.on('pageerror', (err) => pageErrors.push(String(err)))
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    const text = msg.text()
    // 忽略測試容器無外網時的外部字型 DNS 錯誤、全站 auth/me 401 探測，以及連續跑整套 E2E 時的 pageview 429 限流
    if (/ERR_NAME_NOT_RESOLVED/i.test(text)) return
    if (/status of 401 \(Unauthorized\)/i.test(text)) return
    if (/status of 429 \(Too Many Requests\)/i.test(text)) return
    consoleErrors.push(text)
  })
  return { pageErrors, consoleErrors }
}

test.describe('後台管理頁：每日資料庫（md_*）白名單與同步狀態 UI', () => {
  test('白名單讀取、格式防呆、批次新增、儲存持久化、移除並還原（零 JS 錯誤）', async ({ page, request }) => {
    const beforeResp = await request.get('/api/v1/store/whitelist', { headers: h })
    expect(beforeResp.ok()).toBeTruthy()
    const savedBefore = (await beforeResp.json()).data.symbols

    const { pageErrors, consoleErrors } = attachErrorWatchers(page)
    await seedRealAdminSession(page, adminToken)

    // 挑選與原本白名單不重疊的測試代號，確保新增／移除都能明確驗證
    const candidates = ['9991', '9992B', '9993', '9994B']
    const testSyms = candidates.filter((s) => !savedBefore.includes(s)).slice(0, 2)
    expect(testSyms.length).toBe(2)
    const inputBatch = ` ${testSyms[0]} , ${testSyms[1].toLowerCase()}\n${testSyms[0]} `

    try {
      await page.goto('/admin')
      await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
      await page.getByTestId('admin-tab-store').click()

      await expect(page.getByTestId('store-whitelist-section')).toBeVisible()
      await expect(page.getByTestId('store-whitelist-count')).toContainText(`${savedBefore.length} / 100`)

      // 1. 前端格式防呆：少於 4 碼應被擋下並提示錯誤
      await page.getByTestId('store-whitelist-input').fill('23')
      await page.getByTestId('store-whitelist-add-btn').click()
      await expect(page.getByTestId('store-whitelist-error')).toContainText('代號格式不正確')

      // 2. 批次輸入（逗號／空白／換行／小寫／重複）並加入清單
      await page.getByTestId('store-whitelist-input').fill(inputBatch)
      await page.getByTestId('store-whitelist-add-btn').click()
      for (const sym of testSyms) {
        await expect(page.locator(`[data-testid="store-whitelist-tag"][data-symbol="${sym}"]`)).toBeVisible()
      }
      await expect(page.getByTestId('store-whitelist-dirty')).toBeVisible()
      await expect(page.getByTestId('store-whitelist-count')).toContainText(`${savedBefore.length + testSyms.length} / 100`)

      // 3. 儲存白名單，並重新整理頁面驗證持久化
      await page.getByTestId('store-whitelist-save-btn').click()
      await expect(page.getByTestId('store-whitelist-feedback')).toContainText('白名單已儲存')
      await expect(page.getByTestId('store-whitelist-dirty')).toHaveCount(0)

      await page.reload()
      await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
      await page.getByTestId('admin-tab-store').click()
      for (const sym of testSyms) {
        await expect(page.locator(`[data-testid="store-whitelist-tag"][data-symbol="${sym}"]`)).toBeVisible()
      }

      // 4. 移除測試代號並儲存
      for (const sym of testSyms) {
        await page.locator(`[data-testid="store-whitelist-tag"][data-symbol="${sym}"] [data-testid="store-whitelist-remove"]`).click()
        await expect(page.locator(`[data-testid="store-whitelist-tag"][data-symbol="${sym}"]`)).toHaveCount(0)
      }
      await page.getByTestId('store-whitelist-save-btn').click()
      await expect(page.getByTestId('store-whitelist-feedback')).toContainText('白名單已儲存')
      await expect(page.getByTestId('store-whitelist-count')).toContainText(`${savedBefore.length} / 100`)

      // 5. 同步狀態卡片與官方開放資料健康卡片渲染正常（不點擊真正耗額度的手動同步）
      await expect(page.getByTestId('store-status-section')).toBeVisible()
      await expect(page.getByTestId('store-running-badge')).toBeVisible()
      await expect(page.getByTestId('store-run-btn')).toBeVisible()
      for (const ds of ['price', 'institutional', 'margin', 'valuation', 'revenue']) {
        await expect(page.getByTestId(`store-dataset-${ds}`)).toBeVisible()
      }
      await expect(page.getByTestId('store-recent-runs')).toBeVisible()
      await expect(page.getByTestId('open-data-section')).toBeVisible()

      expect(pageErrors).toEqual([])
      expect(consoleErrors).toEqual([])
    } finally {
      const restore = await request.put('/api/v1/store/whitelist', {
        headers: h,
        data: { symbols: savedBefore },
      })
      expect(restore.ok()).toBeTruthy()
    }
  })

  test('空名單時停用手動同步按鈕；有白名單時手動同步走 POST /api/v1/store/run（攔截不耗額度）', async ({ page, request }) => {
    const beforeResp = await request.get('/api/v1/store/whitelist', { headers: h })
    const savedBefore = (await beforeResp.json()).data.symbols

    const { pageErrors, consoleErrors } = attachErrorWatchers(page)
    await seedRealAdminSession(page, adminToken)

    try {
      // 先清空白名單驗證空狀態與按鈕防呆
      await request.put('/api/v1/store/whitelist', { headers: h, data: { symbols: [] } })

      let runCalled = false
      let runAuthHeader = ''
      await page.route('**/api/v1/store/run', async (route) => {
        runCalled = true
        runAuthHeader = route.request().headers()['x-admin-token'] || ''
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: { started: true } }),
        })
      })

      await page.goto('/admin')
      await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
      await page.getByTestId('admin-tab-store').click()

      await expect(page.getByTestId('store-whitelist-empty')).toBeVisible()
      await expect(page.getByTestId('store-run-btn')).toBeDisabled()
      await expect(page.getByTestId('store-run-disabled-reason')).toContainText('白名單為空')

      // 新增 1 檔並儲存後，按鈕應啟用且點擊會打攔截的 POST /api/v1/store/run
      await page.getByTestId('store-whitelist-input').fill('2330')
      await page.getByTestId('store-whitelist-save-btn').click()
      await expect(page.getByTestId('store-whitelist-feedback')).toContainText('白名單已儲存')
      await expect(page.getByTestId('store-run-btn')).toBeEnabled()

      await page.getByTestId('store-run-btn').click()
      await expect.poll(() => runCalled).toBeTruthy()
      expect(runAuthHeader).toBe(adminToken)
      await expect(page.getByTestId('store-run-feedback')).toContainText('已啟動背景增量同步')
      await expect(page.getByTestId('store-running-badge')).toContainText('同步執行中')

      expect(pageErrors).toEqual([])
      expect(consoleErrors).toEqual([])
    } finally {
      await request.put('/api/v1/store/whitelist', {
        headers: h,
        data: { symbols: savedBefore },
      })
    }
  })

  test('6 組色彩主題下每日資料庫管理介面皆可正常切換與渲染，無 JS 錯誤', async ({ page }) => {
    const { pageErrors, consoleErrors } = attachErrorWatchers(page)
    await seedRealAdminSession(page, adminToken)

    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
    await page.getByTestId('admin-tab-store').click()
    await expect(page.getByTestId('store-whitelist-section')).toBeVisible()

    for (const id of ['notebook', 'dark', 'solarized', 'nord', 'dracula', 'gruvbox']) {
      await page.getByTestId('theme-picker-btn').click()
      await page.locator(`[data-theme-id="${id}"]`).click()
      await expect(page.getByTestId('store-whitelist-section')).toBeVisible()
      await expect(page.getByTestId('store-status-section')).toBeVisible()
    }

    expect(pageErrors).toEqual([])
    expect(consoleErrors).toEqual([])
  })
})
