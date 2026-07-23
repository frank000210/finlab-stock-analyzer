// @ts-check
const { test, expect } = require('@playwright/test')

// DD3：後台管理頁的 11 個端點（/admin/settings、/admin/allowed-admins、
// /admin/logs、/admin/llm-usage、/admin/notify/test）先前完全沒有測試覆蓋，
// 只測過「未登入時顯示登入畫面」。這裡分兩塊：
// 1. 後端 require_admin 本身的把關行為——這是真打後端，不用 mock，因為
//    401/403 不需要真的有效的 admin JWT 才能驗證。
// 2. 後台頁面的設定/管理員 CRUD 互動——admin token 是伺服器端用只有
//    process 自己知道的隨機 secret簽的 JWT（沒設 ADMIN_SECRET 時每次啟動
//    都不一樣），測試端不可能生出一個真的能通過驗證的 token，所以這塊
//    改用 localStorage 直接塞一個「看起來已登入」的 admin_user/admin_token
//    （繞過真的 Google OAuth），再 mock 對應的網路請求——驗證的是前端
//    有沒有打對端點、方法、內容，並正確把回應反映到畫面上。

test('後端 require_admin 正確擋掉未帶 token／無效 token 的請求', async ({ request }) => {
  const noToken = await request.get('/api/v1/admin/settings')
  expect(noToken.status()).toBe(401)

  const badToken = await request.get('/api/v1/admin/settings', {
    headers: { 'X-Admin-Token': 'not-a-real-jwt' },
  })
  expect(badToken.status()).toBe(401)

  const badTokenPut = await request.put('/api/v1/admin/settings/some_key', {
    headers: { 'X-Admin-Token': 'not-a-real-jwt' },
    data: { value: 'x' },
  })
  expect(badTokenPut.status()).toBe(401)

  const badTokenAllowedAdmins = await request.get('/api/v1/admin/allowed-admins', {
    headers: { 'X-Admin-Token': 'not-a-real-jwt' },
  })
  expect(badTokenAllowedAdmins.status()).toBe(401)

  const badTokenNotify = await request.post('/api/v1/admin/notify/test', {
    headers: { 'X-Admin-Token': 'not-a-real-jwt' },
    data: { channel: 'telegram', message: 'test' },
  })
  expect(badTokenNotify.status()).toBe(401)
})

async function seedFakeAdminSession(page) {
  await page.addInitScript(() => {
    localStorage.setItem('admin_token', 'fake-token-for-e2e')
    localStorage.setItem('admin_user', JSON.stringify({
      email: 'frank210@gmail.com', name: 'Frank', avatar: '', is_admin: true,
    }))
  })
}

async function mockAdminBootstrap(page) {
  await page.route('**/api/v1/admin/logs/stats', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ success: true, data: { todays_visitors: 3, total_pageviews: 40, unique_visitors: 5 } }),
  }))
  await page.route('**/api/v1/admin/logs*', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: [] }),
  }))
  await page.route('**/api/v1/analytics/pageviews', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({}),
  }))
  await page.route('**/api/v1/admin/llm-usage', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ success: true, data: { days: [], daily_limit: 200, today_count: 0 } }),
  }))
  await page.route('**/api/v1/settings', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { foo: 'bar' } }),
  }))
  await page.route('**/api/v1/admin/allowed-admins', (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: ['frank210@gmail.com'] }) })
    }
    return route.continue()
  })
}

test('後台頁：系統設定新增/更新/刪除都打對端點與方法', async ({ page }) => {
  await seedFakeAdminSession(page)
  await mockAdminBootstrap(page)

  const putCalls = []
  const deleteCalls = []
  let postBody = null
  await page.route('**/api/v1/admin/settings', async (route) => {
    if (route.request().method() === 'POST') {
      postBody = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { foo: 'bar' } }) })
  })
  await page.route('**/api/v1/admin/settings/*', async (route) => {
    if (route.request().method() === 'PUT') { putCalls.push(route.request().url()); return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) }) }
    if (route.request().method() === 'DELETE') { deleteCalls.push(route.request().url()); return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) }) }
    return route.continue()
  })

  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
  await page.getByRole('button', { name: /系統設定/ }).click()

  await page.getByRole('button', { name: '+ 新增' }).click()
  await page.getByPlaceholder('Key').fill('new_flag')
  await page.getByPlaceholder('Value').fill('on')
  await page.getByRole('button', { name: '儲存' }).click()
  expect(postBody).toEqual({ key: 'new_flag', value: 'on' })
  await expect(page.getByText('new_flag')).toBeVisible()

  const fooInput = page.locator('.setting-row', { hasText: 'foo' }).locator('input')
  await fooInput.fill('baz')
  await fooInput.blur()
  expect(putCalls.some((u) => u.includes('/admin/settings/foo'))).toBeTruthy()

  await page.locator('.setting-row', { hasText: 'foo' }).getByRole('button', { name: '刪' }).click()
  expect(deleteCalls.some((u) => u.includes('/admin/settings/foo'))).toBeTruthy()
  await expect(page.locator('.setting-row', { hasText: 'foo' })).toHaveCount(0)
})

test('後台頁：管理員帳號新增/移除都打對端點', async ({ page }) => {
  await seedFakeAdminSession(page)
  await mockAdminBootstrap(page)

  let postBody = null
  let deletedUrl = null
  await page.route('**/api/v1/admin/allowed-admins', async (route) => {
    if (route.request().method() === 'POST') {
      postBody = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: ['frank210@gmail.com'] }) })
  })
  await page.route('**/api/v1/admin/allowed-admins/*', async (route) => {
    if (route.request().method() === 'DELETE') {
      deletedUrl = route.request().url()
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) })
    }
    return route.continue()
  })

  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: '後台管理' })).toBeVisible({ timeout: 20_000 })
  await page.getByRole('button', { name: /^👤 管理員$/ }).click()
  await expect(page.locator('.admin-row', { hasText: 'frank210@gmail.com' })).toBeVisible()

  await page.getByPlaceholder('輸入 Google 帳號 Email').fill('teammate@gmail.com')
  await page.getByRole('button', { name: '新增' }).click()
  expect(postBody).toEqual({ email: 'teammate@gmail.com' })

  // frank210@gmail.com 是目前登入帳號本人，移除鈕理應被停用，避免自己把自己踢出去
  await expect(page.locator('.admin-row', { hasText: 'frank210@gmail.com' }).getByRole('button', { name: '移除' })).toBeDisabled()
})
