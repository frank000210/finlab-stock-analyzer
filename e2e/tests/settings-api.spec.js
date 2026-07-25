// @ts-check
const { test, expect } = require('@playwright/test')

// II10：HH1 修的是 PUT /api/v1/settings 的寫入白名單漏洞——之前這支端點
// 沒驗證、又把 AppSettings 的任何非 None 欄位（含 line_token/finmind_token
// 這種只有管理員該碰的機密）原樣寫進跟 admin.py 共用的同一個 Mongo
// settings collection。HH1 當下只用 curl 手動驗證過，沒有留下自動化測試
// ——之後如果有人不小心把 _WRITABLE_SETTING_KEYS 放寬、或改回直接
// settings.model_dump() 不過濾，不會有任何測試失敗來擋。
//
// 這裡測的是「公開、匿名可打」的觀察面：合法欄位（default_capital）
// PUT 後真的會透過 GET 讀回來；同時夾帶機密欄位（line_token）不會讓合法
// 欄位的寫入壞掉，且 GET 回應中永遠不會出現機密欄位。真正證明 line_token
// 完全沒被寫進 Mongo，需要用管理員權限的 /api/v1/admin/settings 讀回來
// 比對——但 admin JWT 是伺服器啟動時只有 process 自己知道的隨機
// ADMIN_SECRET 簽的，測試端生不出一個能通過驗證的 token（同
// admin-panel.spec.js 的既有限制），所以無法在 e2e 這層直接斷言到那麼深。

test('PUT /api/v1/settings 只寫入白名單欄位，機密欄位不會透過 GET 洩漏', async ({ request }) => {
  const before = await request.get('/api/v1/settings')
  const beforeBody = await before.json()
  const originalCapital = beforeBody?.data?.default_capital

  const probeCapital = 555555
  try {
    const put = await request.put('/api/v1/settings', {
      data: { default_capital: probeCapital, line_token: 'e2e-probe-should-not-persist' },
    })
    expect(put.status()).toBe(200)
    const putBody = await put.json()
    expect(putBody.success).toBe(true)

    const after = await request.get('/api/v1/settings')
    const afterBody = await after.json()
    // 合法欄位確實寫入生效
    expect(afterBody.data.default_capital).toBe(probeCapital)
    // 機密欄位不管有沒有被寫進 Mongo，公開端點的回應裡永遠不該出現
    expect(afterBody.data).not.toHaveProperty('line_token')
    expect(afterBody.data).not.toHaveProperty('finmind_token')
  } finally {
    if (originalCapital != null) {
      await request.put('/api/v1/settings', { data: { default_capital: originalCapital } })
    }
  }
})

test('GET /api/v1/settings 只回傳公開安全子集', async ({ request }) => {
  const resp = await request.get('/api/v1/settings')
  expect(resp.status()).toBe(200)
  const body = await resp.json()
  expect(body.success).toBe(true)
  expect(body.data).not.toHaveProperty('line_token')
  expect(body.data).not.toHaveProperty('finmind_token')
  expect(body.data).not.toHaveProperty('telegram_bot_token')
  expect(body.data).not.toHaveProperty('allowed_admin_emails')
})
