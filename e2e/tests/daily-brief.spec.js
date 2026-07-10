// @ts-check
const { test, expect } = require('@playwright/test')

// C9: watchlist sync + post-close daily brief (also the E14 foundation).
test('同步觀察清單後可產生盤後日報', async ({ request }) => {
  test.setTimeout(120_000)

  const sync = await request.post('/api/v1/risk/sync-watchlist', {
    data: { symbols: ['2330', '2882'] },
  })
  expect(sync.ok()).toBeTruthy()
  expect((await sync.json()).data.count).toBe(2)

  const brief = await request.get('/api/v1/risk/daily-brief', { timeout: 90_000 })
  expect(brief.ok()).toBeTruthy()
  const data = (await brief.json()).data
  expect(data.count).toBeGreaterThan(0)
  expect(data.text).toContain('盤後日報')
  expect(data.text).toContain('2330')
  expect(data.text).toContain('非投資建議')
})

test('日報手動推播端點在未設 Telegram 時優雅回應', async ({ request }) => {
  test.setTimeout(120_000)
  const resp = await request.post('/api/v1/risk/daily-brief/send', { timeout: 90_000 })
  expect(resp.ok()).toBeTruthy()
  const data = (await resp.json()).data
  // 本機未設 bot token：sent=false 且有明確原因（不噴錯）
  expect(typeof data.sent).toBe('boolean')
  if (!data.sent) expect(data.error.length).toBeGreaterThan(0)
})
