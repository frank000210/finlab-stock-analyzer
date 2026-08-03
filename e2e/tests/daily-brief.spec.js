// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// C9: watchlist sync + post-close daily brief (also the E14 foundation).
//
// LL2：/daily-brief、/daily-brief/send 補上跟其他 LLM 端點一致的
// check_llm_rate_limit 後，這兩支測試如果不指定來源 IP，會跟同一輪套件裡
// 其他真的打到後端（非 mock）LLM 呼叫的測試共用同一個「真實 IP」的 6 次/
// 10 分鐘額度——很容易被前面的測試（或人工用 curl 驗證）提早用掉，導致這裡
// 平白 429。比照 Z6/JJ3/JJ5 的作法，用隨機測試 IP 避開共用額度。
const TEST_IP = `203.0.113.${Math.floor(Math.random() * 250) + 1}`

test('同步觀察清單後可產生盤後日報', async ({ request }) => {
  test.setTimeout(120_000)

  const token = await getAdminToken(request)
  const sync = await request.post('/api/v1/risk/sync-watchlist', {
    headers: { 'X-Admin-Token': token },
    data: { symbols: ['2330', '2882'] },
  })
  expect(sync.ok()).toBeTruthy()
  expect((await sync.json()).data.count).toBe(2)

  const brief = await request.get('/api/v1/risk/daily-brief', {
    timeout: 90_000,
    headers: { 'X-Forwarded-For': TEST_IP },
  })
  expect(brief.ok()).toBeTruthy()
  const data = (await brief.json()).data
  expect(data.count).toBeGreaterThan(0)
  expect(data.text).toContain('盤後日報')
  expect(data.text).toContain('2330')
  expect(data.text).toContain('非投資建議')
})

test('日報手動推播端點在未設 Telegram 時優雅回應', async ({ request }) => {
  test.setTimeout(120_000)
  const resp = await request.post('/api/v1/risk/daily-brief/send', {
    timeout: 90_000,
    headers: { 'X-Forwarded-For': TEST_IP },
  })
  expect(resp.ok()).toBeTruthy()
  const data = (await resp.json()).data
  // 本機未設 bot token：sent=false 且有明確原因（不噴錯）
  expect(typeof data.sent).toBe('boolean')
  if (!data.sent) expect(data.error.length).toBeGreaterThan(0)
})
