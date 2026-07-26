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

// KK3：JJ3 幫 analytics.py 的 pageview/user-identify 補上跟 Z6 同一種
// X-Forwarded-For 分桶節流，但先前沒有測試真的打滿門檻驗證 429 會不會觸發，
// 也沒驗證這裡的 _get_client_ip 是不是真的跟 Z6 一樣取最右邊那一段。
test('JJ3 回歸：analytics pageview 端點依 X-Forwarded-For 分桶節流（120 次/10 分鐘）', async ({ request }) => {
  test.setTimeout(60_000)
  const ipA = `203.0.113.${Math.floor(Math.random() * 250) + 1}`
  const ipB = `203.0.113.${Math.floor(Math.random() * 250) + 1}`

  // 最左邊放一個假的偽造值，只有取最右邊那段才會正確分桶到 ipA/ipB。
  const hitOnce = async (ip) => request.post('/api/v1/analytics/pageview', {
    data: { page: '/e2e-jj3-test' },
    headers: { 'X-Forwarded-For': `1.2.3.4, ${ip}` },
  })

  let last
  for (let i = 0; i < 120; i++) {
    last = await hitOnce(ipA)
  }
  expect(last.status()).not.toBe(429)

  const over = await hitOnce(ipA)
  expect(over.status()).toBe(429)

  // 換一個不同的（最右邊）X-Forwarded-For，應該是全新的桶。
  const otherIp = await hitOnce(ipB)
  expect(otherIp.status()).not.toBe(429)
})

// KK4：JJ5 幫 social_buzz.py 的 GET /social-buzz 補上 60 次/10 分鐘的節流，
// 先前沒有測試真的打滿驗證過。用同一檔股票代號重複打，第一次之後的請求
// 會命中快取（不會真的重打 PTT/Google/查核中心），測試才跑得快。
test('JJ5 回歸：social-buzz 端點依 IP 節流（60 次/10 分鐘）', async ({ request }) => {
  test.setTimeout(90_000)
  const ip = `203.0.113.${Math.floor(Math.random() * 250) + 1}`
  const hitOnce = () => request.get('/api/v1/stocks/2330/social-buzz', {
    headers: { 'X-Forwarded-For': ip },
  })

  let last
  for (let i = 0; i < 60; i++) {
    last = await hitOnce()
  }
  expect(last.status()).not.toBe(429)

  const over = await hitOnce()
  expect(over.status()).toBe(429)
})

// KK5：JJ1 幫 graph.py 的 GET /timeline 補上 180 天區間上限，先前沒有測試
// 驗證過——每個日曆日一次的同步 O(symbols²) 運算，超長區間會讓 worker
// 卡住很長一段時間，是真正的 DoS 風險，值得鎖定回歸。
test('JJ1 回歸：類股輪動 timeline 端點超過 180 天區間會被擋下', async ({ request }) => {
  const resp = await request.get(
    '/api/v1/graph/watchlist/timeline?symbols=2330&start=2020-01-01&end=2020-12-31'
  )
  expect(resp.status()).toBe(400)
})

// KK6：CC3 對 backtest 的 AI 生成運算式與 screener 的自然語言選股端點都補上
// 200 字的查詢長度上限（避免 LLM 成本被灌爆），但先前只有其中一支（screener，
// 見 Z6 測試裡故意留空字串繞開真的呼叫 LLM 的手法）有驗證過，backtest 那支
// 從未測過是否真的套用了同一個上限。
test('CC3 回歸：AI 生成運算式與自然語言選股端點都擋下超過 200 字的查詢', async ({ request }) => {
  const longQuery = 'A'.repeat(201)
  // 用隨機測試 IP 避開跟其他 AI 功能測試共用同一把 LLM per-IP 節流額度。
  const ip = `203.0.113.${Math.floor(Math.random() * 250) + 1}`

  const exprResp = await request.post('/api/v1/backtest/generate-expression', {
    data: { query: longQuery },
    headers: { 'X-Forwarded-For': ip },
  })
  expect(exprResp.status()).toBe(400)

  const screenerResp = await request.post('/api/v1/screener/query', {
    data: { query: longQuery },
    headers: { 'X-Forwarded-For': ip },
  })
  expect(screenerResp.status()).toBe(400)
})
