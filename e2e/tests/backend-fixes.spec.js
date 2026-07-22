// @ts-check
const { test, expect } = require('@playwright/test')

// AA9：Z1/Z5/Z6 這幾支後端修正原本完全沒有直接測試覆蓋，只有間接透過會呼叫
// 它們的頁面測試碰到。這裡直接打 API 驗證修正後的行為（Z1 的排程器啟動屬於
// process 生命週期，沒有對外端點可測，改用容器啟動 log 驗證，不在這裡涵蓋）。

test('Z6：LLM 端點的 per-IP 節流依 X-Forwarded-For 分桶，不同來源互不影響', async ({ request }) => {
  // 用隨機測試用 IP（RFC 5737 TEST-NET-3），避免同一 IP_WINDOW_MINUTES=10
  // 分鐘內重跑整個套件（push 完緊接著 merge 都會重跑）時，沿用同一把 key
  // 撞到前一次已經跑滿的計數，導致這次一開始就被擋。
  const ipA = `203.0.113.${Math.floor(Math.random() * 250) + 1}`
  const ipB = `203.0.113.${Math.floor(Math.random() * 250) + 1}`

  // query 故意留空：check_llm_rate_limit 這個 dependency 會先跑完（計入節流
  // 計數），handler 本體才因為空字串在真的呼叫 LLM 之前就先回 400——不需要
  // 真的打 AI API 就能驗證節流本身的行為。
  const hitOnce = async (ip) => request.post('/api/v1/screener/query', {
    data: { query: '' },
    headers: { 'X-Forwarded-For': ip },
  })

  const results = []
  for (let i = 0; i < 6; i++) {
    results.push((await hitOnce(ipA)).status())
  }
  expect(results.every((s) => s !== 429)).toBeTruthy()

  const seventh = await hitOnce(ipA)
  expect(seventh.status()).toBe(429)

  // 換一個不同的 X-Forwarded-For，應該是全新的桶，不會被 ipA 的紀錄卡住——
  // 這正是 Z6 修的行為：換成只看 request.client.host 的話，這裡在同一個
  // container 內打，來源實體連線是同一個，會被誤判成同一把 key 而繼續 429。
  const otherIp = await hitOnce(ipB)
  expect(otherIp.status()).not.toBe(429)
})

test('Z5：/risk/watchlist-signals 與 /risk/sizing 對同一檔股票的 ATR 一致（共用同一份計算）', async ({ request }) => {
  test.setTimeout(120_000)
  // watchlist-signals 除了抓價還會查市值分級（額外 FinMind 呼叫），冷快取
  // 時可能超過預設的 25s action timeout，比照 price-alerts.spec.js 對真實
  // 後端端點的作法拉長逾時。
  const [signalsResp, sizingResp] = await Promise.all([
    request.get('/api/v1/risk/watchlist-signals?symbols=2330', { timeout: 90_000 }),
    request.get('/api/v1/risk/sizing/2330?atr_period=14', { timeout: 90_000 }),
  ])
  expect(signalsResp.ok()).toBeTruthy()
  expect(sizingResp.ok()).toBeTruthy()

  const item = (await signalsResp.json()).data.items.find((it) => it.symbol === '2330')
  const sizing = (await sizingResp.json()).data

  expect(item.ok).toBeTruthy()
  expect(item.stop_dist_pct).not.toBeNull()

  // stop_dist_pct = 2*ATR/price*100 → 反推 ATR，跟 /sizing 直接回傳的 atr
  // 應該幾乎一致（允許兩次個別抓價的極小捨入誤差）。修好 AA5 之前，這兩處
  // 是各自重算一次同一條公式，未來若只改到其中一處就會在這裡被抓到。
  const impliedAtr = (item.stop_dist_pct / 100) * item.price / 2
  expect(Math.abs(impliedAtr - sizing.atr)).toBeLessThan(Math.max(sizing.atr * 0.05, 0.5))
})
