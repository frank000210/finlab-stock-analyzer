// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// 事件研究台（/events）：事件日曆、事件簡報、價格反應、論點抽取、我的決策紀錄。
// API 測試只碰內建資料與自己的 MongoDB；會打 FinMind 的「價格反應」與會呼叫 LLM 的「論點抽取」
// 在畫面測試裡一律用假回應，不消耗額度。計算邏輯由 backend/tests/test_event_desk.py 驗。

const NVDA = '2026-11-12-nvda-ceo-transition'
const TEST_ID = 'e2e-2026-12-01-temp-brief'

let h = {}

test.beforeAll(async ({ request }) => {
  h = { 'X-Admin-Token': await getAdminToken(request) }
})

function minimalBrief(over = {}) {
  return {
    id: TEST_ID,
    title: 'e2e 測試事件',
    kind: 'shock',
    event_date: '2026-12-01',
    as_of: '2026-12-02',
    summary: 'e2e 測試用，跑完會刪掉。',
    facts: [{ text: '一則事實', tier: 2, source_name: '某媒體', source_url: 'https://example.com/a' }],
    key_dates: [{ date: '2026-12-15', label: 'e2e 測試關鍵日' }],
    ...over,
  }
}

// ───────────── API ─────────────

test('日曆：公開、依日期排序、每筆內建事件都有官方來源', async ({ request }) => {
  const r = await request.get('/api/v1/events/calendar?start=2026-11-10&end=2027-02-28')
  expect(r.ok()).toBeTruthy()
  const { events, meta } = (await r.json()).data
  const dates = events.map((e) => e.date)
  expect(dates).toEqual([...dates].sort())
  expect(new Set(events.map((e) => e.id)).size).toBe(events.length)
  expect(meta.verified_on).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  expect(Object.keys(meta.categories)).toContain('fed')

  for (const e of events.filter((x) => x.origin === 'builtin')) {
    expect(e.source_url, e.id).toMatch(/^https:\/\//)
    expect(e.verified_on, e.id).toBeTruthy()
  }
  const nv = events.find((e) => e.id === 'nvda-q3-fy2027')
  expect(nv.date).toBe('2026-11-17')
  expect(nv.tw_reaction_date).toBe('2026-11-18') // 美國時間的事件，台股下一個交易日才反應
  expect(nv.brief_id).toBe(NVDA) // 簡報的關鍵日期掛在同一筆事件上，不重複列

  // 假日順延與連假
  expect(events.find((e) => e.id === 'twfin-2026-11').date).toBe('2026-11-16')
  const lny = events.find((e) => e.id === 'twclosed-2027-02-02')
  expect(lny.end_date).toBe('2027-02-10')
  expect(events.find((e) => e.id === 'us-jobs-2027-02-05').tw_reaction_date).toBe('2027-02-11')
})

test('日曆：類別篩選與參數檢查', async ({ request }) => {
  const r = await request.get('/api/v1/events/calendar?start=2026-11-10&end=2027-02-28&category=fed,macro_us')
  const events = (await r.json()).data.events
  expect(events.length).toBeGreaterThan(3)
  expect(events.every((e) => ['fed', 'macro_us'].includes(e.category))).toBeTruthy()

  expect((await request.get('/api/v1/events/calendar?category=nope')).status()).toBe(400)
  expect((await request.get('/api/v1/events/calendar?start=2026/11/10')).status()).toBe(422)
  expect((await request.get('/api/v1/events/calendar?start=2026-02-30')).status()).toBe(400)
})

test('簡報：列表與內建的輝達簡報（事實分級、未證實有標示、三情境都有推翻條件）', async ({ request }) => {
  const list = (await (await request.get('/api/v1/events/briefs')).json()).data
  const item = list.find((b) => b.id === NVDA)
  expect(item.builtin).toBe(true)
  expect(item.quality_passed).toBe(item.quality_total)

  const r = await request.get(`/api/v1/events/briefs/${NVDA}`)
  expect(r.ok()).toBeTruthy()
  const d = (await r.json()).data
  expect(d.reaction_available).toBe(true)
  expect(d.reaction_symbol_count).toBeGreaterThan(5)
  expect(d.reaction_symbol_count).toBeLessThanOrEqual(20)
  const facts = d.brief.facts
  expect(facts.some((f) => f.tier === 1 && f.source_url.includes('nvidia.com'))).toBeTruthy()
  const unconfirmed = facts.filter((f) => !f.confirmed)
  expect(unconfirmed.length).toBeGreaterThan(0)
  expect(unconfirmed.every((f) => f.tier >= 2)).toBeTruthy()
  expect(d.brief.scenarios.map((s) => s.key).sort()).toEqual(['base', 'bear', 'bull'])
  for (const s of d.brief.scenarios) {
    expect(s.triggers.length).toBeGreaterThan(0)
    expect(s.invalidation.length).toBeGreaterThan(0)
  }
  expect((await request.get('/api/v1/events/briefs/no-such-brief')).status()).toBe(404)
})

test('簡報：模板與格式檢查（不存檔）', async ({ request }) => {
  const t = (await (await request.get('/api/v1/events/briefs/template')).json()).data
  expect(t.template.scenarios.length).toBe(3)
  expect(t.guide.tier).toBeTruthy()

  const bad = await request.post('/api/v1/events/briefs/validate', {
    data: minimalBrief({ facts: [{ text: 'x', tier: 2, source_name: 's', source_url: 'javascript:alert(1)' }] }),
  })
  const badData = (await bad.json()).data
  expect(badData.valid).toBe(false)
  expect(badData.errors.join(' ')).toContain('source_url')

  const ok = (await (await request.post('/api/v1/events/briefs/validate', { data: minimalBrief() })).json()).data
  expect(ok.valid).toBe(true)
  expect(ok.quality.passed).toBeLessThan(ok.quality.total) // 最小簡報缺很多步驟，完整度要如實反映
})

test('寫入要管理員 token；內建簡報不能覆寫或刪除', async ({ request }) => {
  expect((await request.put(`/api/v1/events/briefs/${TEST_ID}`, { data: minimalBrief() })).status()).toBe(401)
  expect((await request.delete(`/api/v1/events/briefs/${TEST_ID}`)).status()).toBe(401)
  expect((await request.post('/api/v1/events/calendar', { data: { date: '2026-12-20', title: 'x' } })).status()).toBe(401)
  expect((await request.delete('/api/v1/events/calendar/c-0000000000')).status()).toBe(401)

  const over = await request.put(`/api/v1/events/briefs/${NVDA}`, { headers: h, data: minimalBrief({ id: NVDA }) })
  expect(over.status()).toBe(409)
  expect((await request.delete(`/api/v1/events/briefs/${NVDA}`, { headers: h })).status()).toBe(409)
})

test('簡報：管理員新增 → 讀得到、關鍵日期進日曆 → 刪除', async ({ request }) => {
  await request.delete(`/api/v1/events/briefs/${TEST_ID}`, { headers: h }) // 清掉上一輪殘留

  const invalid = await request.put(`/api/v1/events/briefs/${TEST_ID}`, { headers: h, data: minimalBrief({ kind: 'rumor' }) })
  expect(invalid.status()).toBe(422)
  expect((await invalid.json()).detail.errors.join(' ')).toContain('kind')
  const mismatch = await request.put('/api/v1/events/briefs/another-id', { headers: h, data: minimalBrief() })
  expect(mismatch.status()).toBe(400)

  const put = await request.put(`/api/v1/events/briefs/${TEST_ID}`, { headers: h, data: minimalBrief() })
  expect(put.ok()).toBeTruthy()
  try {
    const got = (await (await request.get(`/api/v1/events/briefs/${TEST_ID}`)).json()).data
    expect(got.brief.title).toBe('e2e 測試事件')
    expect(got.brief.builtin).toBe(false)
    expect(got.reaction_available).toBe(false)
    const list = (await (await request.get('/api/v1/events/briefs')).json()).data
    expect(list.some((b) => b.id === TEST_ID)).toBeTruthy()
    const cal = (await (await request.get('/api/v1/events/calendar?start=2026-12-14&end=2026-12-16')).json()).data.events
    expect(cal.some((e) => e.brief_id === TEST_ID && e.title === 'e2e 測試關鍵日')).toBeTruthy()
    // 沒設基準日的簡報算不了價格反應，而且不會去打資料源
    expect((await request.get(`/api/v1/events/briefs/${TEST_ID}/reaction`)).status()).toBe(400)
  } finally {
    expect((await request.delete(`/api/v1/events/briefs/${TEST_ID}`, { headers: h })).ok()).toBeTruthy()
  }
  expect((await request.get(`/api/v1/events/briefs/${TEST_ID}`)).status()).toBe(404)
})

test('自訂日曆事件：新增 → 出現在日曆 → 刪除；內建事件不能刪', async ({ request }) => {
  const add = await request.post('/api/v1/events/calendar', {
    headers: h,
    data: { date: '2026-12-19', title: 'e2e 自訂事件', category: 'earnings', importance: 1, source_url: 'https://example.com/ir' },
  })
  expect(add.ok()).toBeTruthy()
  const id = (await add.json()).data.id
  expect(id).toMatch(/^c-/)
  try {
    const cal = (await (await request.get('/api/v1/events/calendar?start=2026-12-18&end=2026-12-22')).json()).data.events
    const row = cal.find((e) => e.id === id)
    expect(row.origin).toBe('custom')
    expect(row.tw_reaction_date).toBe('2026-12-21') // 12/19 是星期六
  } finally {
    expect((await request.delete(`/api/v1/events/calendar/${id}`, { headers: h })).ok()).toBeTruthy()
  }
  expect((await request.delete(`/api/v1/events/calendar/${id}`, { headers: h })).status()).toBe(404)
  expect((await request.delete('/api/v1/events/calendar/nvda-q3-fy2027', { headers: h })).status()).toBe(400)
  const bad = await request.post('/api/v1/events/calendar', { headers: h, data: { date: '2026-12-19', title: 'x', source_url: 'javascript:1' } })
  expect(bad.status()).toBe(422)
})

test('論點抽取：內容太短直接擋下（不呼叫 AI）', async ({ request }) => {
  const r = await request.post('/api/v1/events/claims/extract', { data: { text: '太短了', source: 'x' } })
  expect(r.status()).toBe(400)
  expect((await r.json()).detail).toContain('太短')
})

// ───────────── 畫面 ─────────────

test('事件研究台：日曆可篩選、分頁可切換、側邊欄有入口', async ({ page }) => {
  await page.goto('/events')
  await expect(page.getByRole('heading', { name: '事件研究台', level: 1 })).toBeVisible()
  await expect(page.locator('.sidebar-nav').getByRole('link', { name: '事件研究台' })).toBeVisible()

  const cal = page.getByTestId('ev-calendar')
  await expect(cal.locator('.ev-row').first()).toBeVisible()
  const statutory = cal.locator('.ev-row[data-event-id^="twrev-"]')
  await expect(statutory.first()).toBeVisible()
  await cal.getByRole('button', { name: '台股法定公告期限' }).click()
  await expect(statutory).toHaveCount(0)
  await cal.getByRole('button', { name: '台股法定公告期限' }).click()
  await expect(statutory.first()).toBeVisible()

  await page.getByRole('tab', { name: '事件簡報' }).click()
  await expect(page).toHaveURL(/tab=briefs/)
  await expect(page.getByTestId('ev-briefs').locator(`[data-brief-id="${NVDA}"]`)).toBeVisible()
  // 沒登入看不到管理員的編輯器
  await expect(page.getByTestId('ev-editor')).toHaveCount(0)
})

test('Ctrl+K 搜得到事件研究台', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Control+k')
  const panel = page.locator('.qs-panel')
  await expect(panel).toBeVisible()
  await page.locator('.qs-input').fill('事件研究')
  await expect(panel.locator('.qs-item').first()).toContainText('事件研究台')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/events$/)
})

// 價格反應會打 FinMind：畫面測試一律用這份假回應（含一檔抓不到資料的情形）
async function mockReaction(page) {
  const calls = { n: 0 }
  await page.route(`**/api/v1/events/briefs/${NVDA}/reaction`, async (route) => {
    calls.n += 1
    const row = (symbol, name, day1, latest, excess) => ({
      symbol, name, group: '測試族群', order: 2, direction: 'mixed',
      base_date: '2026-11-12', base_close: 100, days_since: 1, day1_date: '2026-11-13', day1_pct: day1,
      latest_date: '2026-11-13', latest_close: 100, latest_pct: latest, pre_pct: -3.2, pre_low_pct: -9.9,
      pre_low_date: '2026-11-06', episode_from: '2026-10-30', vol_ratio_day1: 0.85, ma20: 99, ma60: 101,
      above_ma20: true, above_ma60: false, path: [], day1_excess: excess, latest_excess: excess, pre_excess: 0,
    })
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: {
        brief_id: NVDA, base_date: '2026-11-12', episode_start: '2026-10-30', as_of: '2026-11-14', cached: false,
        complete: false, errors: { 3324: '價格取得失敗' }, note: '事後量測，不是訊號。',
        bench: { ...row('TAIEX', '', 1.35, 1.35, null), base_close: 43091.87 },
        rows: [row('2330', '台積電', 0.43, 0.43, -0.92), { symbol: '3324', name: '雙鴻', group: '散熱與電源', error: '沒有價格資料' }],
      } }),
    })
  })
  return calls
}

test('事件簡報頁：六塊內容齊全，價格反應要按了才抓', async ({ page }) => {
  const reaction$ = await mockReaction(page)

  await page.goto(`/events/briefs/${NVDA}`)
  await expect(page.getByRole('heading', { name: '輝達執行長黃仁勳辭任', level: 1 })).toBeVisible()
  const facts = page.getByTestId('eb-facts')
  await expect(facts.getByText('官方第一手').first()).toBeVisible()
  await expect(facts.getByText('未證實').first()).toBeVisible()
  await expect(page.getByTestId('eb-expectation')).toContainText('落差在哪裡')
  await expect(page.getByTestId('eb-impact')).toContainText('二階：供應鏈與客戶')
  await expect(page.getByTestId('eb-impact').getByRole('link', { name: /2330 台積電/ })).toHaveAttribute('href', '/stocks/2330')
  const scen = page.getByTestId('eb-scenarios')
  await expect(scen.locator('.eb-scen-card')).toHaveCount(3)
  await expect(scen).toContainText('看到什麼代表這個情境不成立')
  await expect(page.getByTestId('eb-next')).toContainText('2026-11-17')
  await expect(page.getByTestId('eb-viewpoints')).toBeVisible()

  await page.getByTestId('eb-quality').locator('summary').click()
  await expect(page.getByTestId('eb-quality').locator('li.ok')).toHaveCount(9)

  expect(reaction$.n).toBe(0)
  const reaction = page.getByTestId('eb-reaction')
  await reaction.getByRole('button', { name: '計算價格反應' }).click()
  await expect(reaction.locator('tr.bench')).toContainText('+1.35%')
  expect(reaction$.n).toBe(1)
  const tsmc = reaction.locator('tbody tr', { hasText: '2330 台積電' })
  await expect(tsmc).toContainText('-0.92%')
  await expect(tsmc).toContainText('站上月線、跌破季線')
  await expect(tsmc.locator('td.down').first()).toBeVisible() // 跌用綠色（台股慣例）
  await expect(reaction.locator('tbody tr', { hasText: '3324 雙鴻' })).toContainText('沒有價格資料')
  await expect(reaction).toContainText('30 分鐘後再試')
})

test('我的決策紀錄：只存在瀏覽器，到檢討日會提醒', async ({ page }) => {
  await page.goto(`/events/briefs/${NVDA}`)
  const box = page.getByTestId('eb-decision')
  await box.getByLabel('我打算').selectOption('watch')
  await box.getByLabel('最多可承受虧損（占總資金 %）').fill('1')
  await box.getByLabel('哪一天回頭檢討').fill('2026-01-05') // 已經過去的日期 → 立刻到期
  await box.getByLabel('理由（我是根據哪個情境、哪些事實）').fill('基準情境：等財報後再決定')
  await box.getByLabel('什麼情況代表我看錯了（價位或事件都可以）').fill('財測明顯低於共識')
  await box.getByRole('button', { name: '記下來' }).click()

  const item = box.locator('.eb-decisions li').first()
  await expect(item).toContainText('觀察，等訊號出現再說')
  await expect(item).toContainText('最多賠 1%')
  await expect(item).toContainText('到期待檢討')

  await page.reload()
  await expect(page.getByTestId('eb-decision').locator('.eb-decisions li')).toHaveCount(1)
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_event_decisions_v1') || '[]'))
  expect(stored).toHaveLength(1)
  expect(stored[0].brief_id).toBe(NVDA)

  await page.goto('/events')
  await expect(page.getByTestId('ev-due')).toContainText('1 筆決策紀錄到了')
  await page.getByTestId('ev-due').click()
  await expect(page).toHaveURL(new RegExp(`/events/briefs/${NVDA}`))

  const again = page.getByTestId('eb-decision').locator('.eb-decisions li').first()
  await again.getByPlaceholder(/檢討：結果如何/).fill('當初的理由成立，但太晚動作')
  await again.getByRole('button', { name: '標記已檢討' }).click()
  await expect(again).toContainText('已檢討')
  await expect(again).toContainText('當初的理由成立')
  await page.goto('/events')
  await expect(page.getByTestId('ev-due')).toHaveCount(0)
})

test('論點抽取：原句對不上的會被標出來', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  let body = null
  await page.route('**/api/v1/events/claims/extract', async (route) => {
    body = route.request().postDataJSON()
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: {
        stance: '偏多', source: '某頻道', cached: false, chars: 400, as_of: '2026-11-14', missing: ['沒有說自己的持股'],
        stats: { total: 2, quote_verified: 1, quote_unverified: 1, with_invalidation: 1, forecasts: 1, checkable: 1 },
        claims: [
          { claim: '下一季營收會成長', quote: '我認為下一季的營收還是會成長', quote_match: 'exact', kind: 'forecast',
            assumptions: ['雲端大廠資本支出不下修'], invalidation: '財測低於一千億美元', horizon: '下一季', checkable: true, check_how: '看財報的財測' },
          { claim: '股價會到 300 美元', quote: '明年股價會漲到三百美元以上', quote_match: 'none', kind: 'opinion',
            assumptions: [], invalidation: '', horizon: '', checkable: false, check_how: '' },
        ],
      } }),
    })
  })

  await page.goto('/events?tab=claims')
  const box = page.getByTestId('ev-claims')
  const btn = box.getByRole('button', { name: '抽出論點' })
  await expect(btn).toBeDisabled() // 還沒貼內容
  await box.getByLabel('來源（選填，方便你自己辨識）').fill('某頻道')
  await box.getByLabel('逐字稿或文章內容').fill('我認為下一季的營收還是會成長。'.repeat(20))
  await expect(btn).toBeEnabled()
  await btn.click()

  const result = page.getByTestId('ev-claims-result')
  await expect(result).toContainText('共 2 條論點')
  await expect(result).toContainText('對不上 1 條')
  await expect(result.locator('.ev-quote.exact')).toContainText('原文找得到')
  await expect(result.locator('.ev-quote.none')).toContainText('原文找不到這句')
  await expect(result).toContainText('講者沒說')
  await expect(result).toContainText('沒有說自己的持股')
  expect(body.source).toBe('某頻道')
  expect(body.text.length).toBeGreaterThanOrEqual(200)
})

test('手機寬度：事件研究台與簡報頁（含很寬的價格反應表）不會左右捲動', async ({ page }) => {
  await mockReaction(page)
  await page.setViewportSize({ width: 375, height: 812 })
  const overflow = () => page.evaluate(() => {
    const el = document.scrollingElement
    return el.scrollWidth - el.clientWidth
  })

  await page.goto('/events')
  await expect(page.locator('h1').first()).toBeVisible()
  await expect(page.getByTestId('ev-calendar').locator('.ev-row').first()).toBeVisible()
  expect(await overflow(), '/events').toBeLessThanOrEqual(1)

  await page.goto(`/events/briefs/${NVDA}`)
  const reaction = page.getByTestId('eb-reaction')
  await reaction.getByRole('button', { name: '計算價格反應' }).click()
  await expect(reaction.locator('tr.bench')).toBeVisible()
  expect(await overflow(), '簡報頁').toBeLessThanOrEqual(1)
  // 表格本身可以左右捲（內容比容器寬），只是不能撐破整頁
  const wrap = await reaction.locator('.table-wrap').evaluate((el) => ({ sw: el.scrollWidth, cw: el.clientWidth }))
  expect(wrap.sw).toBeGreaterThan(wrap.cw)
})
