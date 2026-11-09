// @ts-check
const { test, expect } = require('@playwright/test')

// 個股三面向評分卡（個股分析頁）。評分卡端點 mock：這支測試驗證「前端怎麼呈現、怎麼與 AI 決策評分共用一份資料」，
// 每個檢核項的算法與門檻由 backend/tests/test_stock_scorecard.py 負責（含真實資料對帳）。
// 頁面其他部分（價格、財報…）照其他分析頁測試的慣例打真的後端。

const LABELS = {
  fundamental: ['本益比為正，且不高於自身近 3 年中位數', '股價淨值比不高於自身近 3 年中位數', '現金殖利率 ≥ 3%', '月營收創 10 個月新高',
    '近 3 月平均營收年增率 > 0', '最近一季營業利益 > 0', '最近一季稅後淨利 > 0', '近四季 EPS 合計 > 前四季合計', '近四季 ROE ≥ 8%', '毛利率不低於去年同期'],
  technical: ['收盤 > 5 日均線（週線）', '收盤 > 20 日均線（月線）', '20 日均線 > 60 日均線（月線在季線上）', '均線多頭排列（5 > 10 > 20）', 'MACD 的 DIF > DEA',
    'RSI14 在 50～70（多頭且未過熱）', 'KD 近 3 日黃金交叉且 K < 80', '量增收漲（量 ≥ 20 日均量 1.2 倍且收盤上漲）', '近 3 日累計漲幅勝過加權指數', '收盤創 60 日新高'],
  chip: ['外資近 5 日淨買超', '外資連買 2 日以上', '投信近 5 日淨買超', '外資、投信近 5 日有 2 日以上同日買超', '三大法人近 20 日合計淨買超',
    '千張大戶持股比本週增加', '集保結構偏多（大戶集中、散戶低）', '近 5 日融資餘額未增加', '近 5 日當沖比 < 30%（非投機過熱）', '外資持股比例近 20 日上升'],
}
const PREFIX = { fundamental: 'F', technical: 'T', chip: 'C' }
const NAMES = { fundamental: '基本面', technical: '技術面', chip: '籌碼面' }

/** statuses：每個面向 10 個 'p'|'f'|'n'（通過／未通過／不適用） */
function dimension(key, statuses, period = '') {
  const items = LABELS[key].map((label, i) => {
    const s = statuses[i]
    const status = s === 'p' ? 'pass' : s === 'f' ? 'fail' : 'na'
    return {
      id: `${PREFIX[key]}${i + 1}`, label, status,
      value: status === 'na' ? '—' : `${label.slice(0, 4)}的實際值 ${i + 1}`,
      threshold: status === 'na' ? '' : `門檻 ${i + 1}`,
      note: status === 'na' ? '資料不足' : '',
    }
  })
  const decidable = items.filter(i => i.status !== 'na').length
  const passed = items.filter(i => i.status === 'pass').length
  const score10 = decidable >= 5 ? Math.round((passed / decidable) * 100) / 10 : null
  return { key, label: NAMES[key], items, passed, decidable, total: 10, score10, score100: score10 == null ? null : Math.round(score10 * 10), period }
}

function card(overrides = {}) {
  const fundamental = dimension('fundamental', ['p', 'f', 'f', 'f', 'p', 'p', 'p', 'p', 'p', 'p'], '2026Q2')   // 7/10
  const technical = dimension('technical', ['p', 'f', 'f', 'f', 'f', 'f', 'p', 'f', 'p', 'f'])                 // 3/10
  const chip = dimension('chip', ['f', 'f', 'p', 'f', 'f', 'n', 'n', 'p', 'p', 'f'])                           // 3/8
  return {
    version: 'v1', applicable: true, symbol: '2330', name: '台積電',
    dimensions: [fundamental, technical, chip],
    total: { passed: 13, decidable: 28, total: 30, score30: 13.8 },
    label: { text: '體質佳・等待進場', tone: 'flat', note: '現況描述，不是預測；門檻尚未經回測驗證。' },
    scores: { technical: technical.score100, fundamental: fundamental.score100, chip: chip.score100 },
    flags: [
      { id: 'above_ma240', tone: 'info', text: '站上年線且年線上揚（長線趨勢向上）。' },
      { id: 'overextended', tone: 'warn', text: '短線乖離偏大（RSI 78），追價風險較高。' },
    ],
    meta: { financial_period: '2026Q2', revenue_month: '2026-09', price_date: '2026-11-09', industry: '半導體業', chip_available: true, failed: [] },
    ...overrides,
  }
}

/** @param {import('@playwright/test').Page} page */
async function mockScorecard(page, body, calls = [], status = 200) {
  await page.route('**/api/v1/analysis/*/scorecard', async (route) => {
    calls.push(route.request().url())
    await route.fulfill({
      status, contentType: 'application/json',
      body: JSON.stringify(status === 200 ? { success: true, data: body } : { detail: body }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { try { localStorage.setItem('finlab_onboarded', '1') } catch {} })
})

test('個股分析頁顯示三面向評分卡：三欄各 10 項、面向分數、總分、標籤、旗標與資料期別', async ({ page }) => {
  await mockScorecard(page, card())
  await page.goto('/stocks/2330')

  const sc = page.getByTestId('scorecard')
  await expect(sc).toBeVisible({ timeout: 60_000 })
  for (const key of ['fundamental', 'technical', 'chip']) {
    await expect(page.getByTestId(`sc-dim-${key}`).locator('[data-testid^="sc-item-"]')).toHaveCount(10)
  }
  await expect(page.getByTestId('sc-dim-score-fundamental')).toHaveText('7/10')
  await expect(page.getByTestId('sc-dim-score-technical')).toHaveText('3/10')
  await expect(page.getByTestId('sc-dim-score-chip')).toHaveText('3/8')            // 2 項不適用，不計入分母
  await expect(page.getByTestId('sc-dim-chip')).toContainText('2 項不適用')
  await expect(page.getByTestId('scorecard-total')).toContainText('13')
  await expect(page.getByTestId('scorecard-total')).toContainText('/ 28')
  await expect(page.getByTestId('scorecard-label')).toHaveText('體質佳・等待進場')
  await expect(page.getByTestId('scorecard-meta')).toContainText('財報 2026Q2')
  await expect(page.getByTestId('scorecard-meta')).toContainText('月營收 2026-09')
  await expect(page.getByTestId('sc-flag')).toHaveCount(2)
  await expect(page.locator('[data-flag="overextended"]')).toContainText('追價風險')
  await expect(sc).toContainText('不是預測')

  // 「怎麼用」說明預設收合、點開看得到 7 點
  const howto = page.getByTestId('sc-howto')
  await expect(howto).not.toHaveAttribute('open', '')
  await howto.locator('summary').click()
  await expect(howto.locator('li')).toHaveCount(7)
  await expect(howto).toContainText('基本面當門檻')
})

test('每個檢核項標示通過／未通過／不適用，附實際值與門檻；不適用不是 0 分', async ({ page }) => {
  await mockScorecard(page, card())
  await page.goto('/stocks/2330')
  await expect(page.getByTestId('scorecard')).toBeVisible({ timeout: 60_000 })

  const f1 = page.getByTestId('sc-item-F1')
  await expect(f1).toHaveAttribute('data-status', 'pass')
  await expect(f1).toContainText('實際值 1')
  await expect(f1).toContainText('門檻：門檻 1')
  await expect(f1.locator('.sc-ico')).toHaveText('✓')
  await expect(page.getByTestId('sc-item-F2')).toHaveAttribute('data-status', 'fail')
  await expect(page.getByTestId('sc-item-F2').locator('.sc-ico')).toHaveText('✗')
  const na = page.getByTestId('sc-item-C6')
  await expect(na).toHaveAttribute('data-status', 'na')
  await expect(na.locator('.sc-ico')).toHaveText('—')
  await expect(na).toContainText('資料不足')
  // 讀屏用的文字也帶狀態（不只靠符號與顏色）
  await expect(f1.locator('.sr-only')).toHaveText('符合：')
  await expect(page.getByTestId('sc-item-F2').locator('.sr-only')).toHaveText('不符合：')
})

test('AI 決策評分的技術／基本／籌碼三項來自評分卡的通過率，說明文字與評分卡一致', async ({ page }) => {
  await mockScorecard(page, card())
  await page.goto('/stocks/2330')
  await expect(page.getByTestId('scorecard')).toBeVisible({ timeout: 60_000 })

  const row = name => page.locator('.score-list .score-item', { hasText: name })
  await expect(row('技術面').locator('.score-item-head strong')).toHaveText('30')      // 3/10 → 30
  await expect(row('基本面').locator('.score-item-head strong')).toHaveText('70')      // 7/10 → 70
  await expect(row('籌碼面').locator('.score-item-head strong')).toHaveText('38')      // 3/8 → 37.5 → 38
  await expect(row('技術面')).toContainText('評分卡通過 3 / 10 項')
  await expect(row('籌碼面')).toContainText('評分卡通過 3 / 8 項')
})

test('某面向可判定項目太少時顯示「資料不足」、決策評分以中性 50 計', async ({ page }) => {
  const thin = dimension('chip', ['p', 'f', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n'])     // 只有 2 項可判定
  const base = card()
  const dims = [base.dimensions[0], base.dimensions[1], thin]
  await mockScorecard(page, card({
    dimensions: dims, scores: { technical: 30, fundamental: 70, chip: null },
    label: { text: '資料不足', tone: 'flat', note: '籌碼面可判定的項目太少。現況描述，不是預測。' },
    total: { passed: 11, decidable: 22, total: 30, score30: null },
  }))
  await page.goto('/stocks/2330')
  await expect(page.getByTestId('scorecard')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId('sc-dim-score-chip')).toHaveText('資料不足')
  await expect(page.getByTestId('scorecard-label')).toHaveText('資料不足')
  await expect(page.locator('.score-list .score-item', { hasText: '籌碼面' }).locator('.score-item-head strong')).toHaveText('50')
  await expect(page.locator('.score-list .score-item', { hasText: '籌碼面' })).toContainText('資料不足，視為中性')
})

test('ETF：評分卡說明不適用並導向 ETF 比較頁，不顯示三欄', async ({ page }) => {
  await mockScorecard(page, { version: 'v1', applicable: false, symbol: '0050', reason: 'ETF 沒有財報與個股籌碼，請改用「ETF 比較」頁。' })
  await page.goto('/stocks/0050')
  const na = page.getByTestId('scorecard-na')
  await expect(na).toBeVisible({ timeout: 60_000 })
  await expect(na).toContainText('ETF 沒有財報')
  await expect(na.getByRole('link', { name: '前往 ETF 比較' })).toHaveAttribute('href', '/etf-compare')
  await expect(page.locator('[data-testid^="sc-dim-"]')).toHaveCount(0)
})

test('評分卡載入失敗：只在卡片位置顯示原因與重試，AI 決策評分退回原算法；重試成功後換成評分卡', async ({ page }) => {
  const calls = []
  let attempt = 0
  await page.route('**/api/v1/analysis/*/scorecard', async (route) => {
    attempt += 1
    calls.push(route.request().url())
    if (attempt === 1) {
      // 用 429（被限流）：fetchWithRetry 對 5xx 會自動重試、4xx 不重試，所以 5xx 的失敗畫面看不到
      await route.fulfill({ status: 429, contentType: 'application/json', body: JSON.stringify({ detail: '查詢過於頻繁，請約 2 分鐘後再試。' }) })
    } else {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: card() }) })
    }
  })
  await page.goto('/stocks/2330')

  await expect(page.getByTestId('scorecard-error')).toContainText('查詢過於頻繁', { timeout: 60_000 })
  await expect(page.locator('.hero-card')).toBeVisible()                       // 頁面其他部分不受影響
  await expect(page.locator('.score-list .score-item', { hasText: '技術面' })).not.toContainText('評分卡通過')

  await page.getByTestId('scorecard-retry').click()
  await expect(page.getByTestId('scorecard-label')).toHaveText('體質佳・等待進場')
  await expect(page.getByTestId('scorecard-error')).toHaveCount(0)
  await expect(page.locator('.score-list .score-item', { hasText: '技術面' })).toContainText('評分卡通過 3 / 10 項')
  expect(calls).toHaveLength(2)
})

test('美股不載入評分卡：沒有請求、也不顯示這一區', async ({ page }) => {
  const calls = []
  await mockScorecard(page, card(), calls)
  await page.goto('/stocks/AAPL')
  await expect(page.locator('.hero-card')).toBeVisible({ timeout: 60_000 })
  await page.waitForTimeout(1500)
  expect(calls).toEqual([])
  await expect(page.getByTestId('scorecard-section')).toHaveCount(0)
})

test('換股會清掉上一檔的評分卡，再依新代號重新載入', async ({ page }) => {
  const calls = []
  await page.route('**/api/v1/analysis/*/scorecard', async (route) => {
    calls.push(route.request().url())
    const sym = route.request().url().split('/analysis/')[1].split('/')[0]
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: card({ symbol: sym, label: { text: `標籤 ${sym}`, tone: 'flat', note: '現況描述，不是預測。' } }) }),
    })
  })
  await page.goto('/stocks/2330')
  await expect(page.getByTestId('scorecard-label')).toHaveText('標籤 2330', { timeout: 60_000 })
  await page.goto('/stocks/2317')
  await expect(page.getByTestId('scorecard-label')).toHaveText('標籤 2317', { timeout: 60_000 })
  expect(calls.map(u => u.split('/analysis/')[1].split('/')[0])).toEqual(['2330', '2317'])
})

test('手機：三欄改單欄堆疊，評分卡不撐寬', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockScorecard(page, card())
  await page.goto('/stocks/2330')
  await expect(page.getByTestId('scorecard')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('scorecard').scrollIntoViewIfNeeded()

  const boxes = await Promise.all(['fundamental', 'technical', 'chip'].map(k => page.getByTestId(`sc-dim-${k}`).boundingBox()))
  expect(boxes[1].y).toBeGreaterThan(boxes[0].y + boxes[0].height - 2)       // 由上往下堆疊，不是並排
  expect(boxes[2].y).toBeGreaterThan(boxes[1].y + boxes[1].height - 2)
  for (const b of boxes) expect(b.x + b.width).toBeLessThanOrEqual(390)
  // 只檢查評分卡自己不撐寬（分析頁別處的 D3 日曆圖在手機上本來就比螢幕寬，不是這張卡造成的）
  const cardOverflow = await page.getByTestId('scorecard-section').evaluate(el => el.scrollWidth - el.clientWidth)
  expect(cardOverflow).toBeLessThanOrEqual(1)
})

test('桌機：三欄並排', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 900 })
  await mockScorecard(page, card())
  await page.goto('/stocks/2330')
  await expect(page.getByTestId('scorecard')).toBeVisible({ timeout: 60_000 })
  const boxes = await Promise.all(['fundamental', 'technical', 'chip'].map(k => page.getByTestId(`sc-dim-${k}`).boundingBox()))
  expect(Math.abs(boxes[0].y - boxes[1].y)).toBeLessThan(2)
  expect(Math.abs(boxes[1].y - boxes[2].y)).toBeLessThan(2)
  expect(boxes[1].x).toBeGreaterThan(boxes[0].x + boxes[0].width - 2)
})
