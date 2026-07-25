// @ts-check
const { test, expect } = require('@playwright/test')

// GG10：signal_rules.py 的 PUT /{id} 與 POST /{id}/activate 先前完全沒有
// 打過真實後端的測試（既有測試都是 page.route() 全 mock）。這裡直接呼叫
// 真正的端點，驗證更新與啟用/停用確實生效，結束後清乾淨（刪除測試規則、
// 把 default 規則重新設回啟用），避免污染其他測試或手動操作的狀態。

test('PUT /api/v1/signal-rules/{id} 與 POST /activate 對真實後端生效', async ({ request }) => {
  const created = await request.post('/api/v1/signal-rules', {
    data: {
      name: 'e2e-api-test-rule',
      description: '初始描述',
      script: 'signal = "HOLD"\nconfidence = 0.5\nconditions = []\nreasoning = "placeholder"',
    },
  })
  expect(created.status()).toBe(200)
  const createdBody = await created.json()
  expect(createdBody.success).toBe(true)
  const ruleId = createdBody.data.id

  try {
    const updated = await request.put(`/api/v1/signal-rules/${ruleId}`, {
      data: { name: 'e2e-api-test-rule-updated', description: '更新後描述' },
    })
    expect(updated.status()).toBe(200)
    const updatedBody = await updated.json()
    expect(updatedBody.success).toBe(true)
    expect(updatedBody.data.name).toBe('e2e-api-test-rule-updated')
    expect(updatedBody.data.description).toBe('更新後描述')

    const activated = await request.post(`/api/v1/signal-rules/${ruleId}/activate`)
    expect(activated.status()).toBe(200)
    const activatedBody = await activated.json()
    expect(activatedBody.success).toBe(true)
    expect(activatedBody.data.isActive).toBe(true)

    const list = await request.get('/api/v1/signal-rules')
    const listBody = await list.json()
    const items = listBody.data.items
    const thisRule = items.find((r) => r.id === ruleId)
    const defaultRule = items.find((r) => r.isDefault)
    expect(thisRule.isActive).toBe(true)
    expect(defaultRule.isActive).toBe(false)
  } finally {
    await request.delete(`/api/v1/signal-rules/${ruleId}`)
    const defaultRule = (await (await request.get('/api/v1/signal-rules')).json()).data.items.find((r) => r.isDefault)
    if (defaultRule && !defaultRule.isActive) {
      await request.post(`/api/v1/signal-rules/${defaultRule.id}/activate`)
    }
  }
})

// GG10：cache.py 的 /stats 與 DELETE 先前零測試覆蓋，包含 require_admin
// 驗證關卡本身有沒有生效都沒人測過。跟 admin-panel.spec.js 同樣的作法
// ——只驗證「沒帶 token 會被擋下」，不用真的產生一組通過驗證的 JWT。
// 刻意不測 /reingest：那支端點會觸發真正的類股輪動+關聯圖全量重抓（打
// 真實 FinMind API），5 分鐘冷卻時間本身就是為了避免被重複觸發的昂貴
// 操作，不適合在每次跑測試套件時都真的觸發一次。

test('後端 cache.py 的 /stats 與 DELETE 正確擋掉未帶 token 的請求', async ({ request }) => {
  const stats = await request.get('/api/v1/cache/stats')
  expect(stats.status()).toBe(401)

  const del = await request.delete('/api/v1/cache')
  expect(del.status()).toBe(401)
})
