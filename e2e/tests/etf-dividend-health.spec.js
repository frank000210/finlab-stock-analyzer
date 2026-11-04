// @ts-check
const { test, expect } = require('@playwright/test')

// 配息體檢（高殖利率撐不撐得住）。後端 API 全部 mock：這支驗證「前端怎麼呈現」——總評、
// 四項檢查、情境殖利率、不足時的說明、不配息不顯示；數字的正確性由
// backend/tests/test_etf_dividend_health.py 負責，也避免 e2e 打 FinMind。

const DATES = ['2025-11-03', '2025-11-04', '2025-11-05', '2025-11-06']

function base(symbol, name, category, o = {}) {
  const pays = o.pays !== false
  return {
    symbol, name, category,
    metrics: { first_date: '2021-05-03', history_days: 1300, last_close: 20, last_date: '2026-10-30', return_1y: 0.1, cagr_3y: 0.1, ann_return: 0.1, ann_vol: 0.2, sharpe: 1, mdd: -0.1, short_history: false, window_days: 242 },
    dividends: { pays_dividend: pays, yield_ttm: pays ? 0.08 : null, ttm_amount: pays ? 1.6 : 0, by_year: [], events: [] },
    fill: { n: 0, filled: 0, failed: 0, pending: 0, avg_days: null, success_rate: null, events: [] },
    scores: { return: 50, defense: 50, sharpe: 50, yield: pays ? 80 : null, fill: null, total: 60, return_basis: 'cagr_3y' },
    series: { dates: DATES, adj: [100, 101, 102, 103] },
    splits: [],
    event: null,
    health: o.health ?? null,
  }
}

const WEAK = {
  enough: true, reason: null, verdict: 'weak', verdict_label: '偏弱', freq: 4, freq_label: '季配',
  last_close: 20, avg_close_ttm: 26, yield_now: 0.08, yield_norm: 0.0615, inflation: 1.3, ttm_amount: 1.6,
  payouts: [
    { date: '2025-10-20', amount: 0.5 }, { date: '2026-01-20', amount: 0.5 },
    { date: '2026-04-20', amount: 0.4 }, { date: '2026-07-20', amount: 0.2 },
  ],
  stability: { n: 4, mean: 0.4, min: 0.2, max: 0.5, cv: 0.3 },
  trend: { basis: 'yoy', last: 0.2, ref: 0.5, ratio: 0.4 },
  principal: { years: 3, price_return: -0.3, total_return: -0.05, dist_contribution: 0.25, erosion: 1.2 },
  scenarios: { freq: 4, freq_label: '季配', conservative: 0.04, neutral: 0.08, last_annualized: 0.04 },
  checks: [
    { key: 'inflation', label: '殖利率膨脹', level: 'warn', text: '現價殖利率 8.0%，若股價在近 12 個月平均價則為 6.2%。' },
    { key: 'stability', label: '配息穩定度', level: 'warn', text: '最近 4 次配息 0.200～0.500 元，變異度 30%。' },
    { key: 'trend', label: '近期趨勢', level: 'bad', text: '最近一次配 0.200 元，相較去年同期 0.500 元減少 60%。' },
    { key: 'principal', label: '吃本金檢查', level: 'bad', text: '近 3.0 年價格 -30.0%、含息 -5.0%。' },
  ],
}
const STEADY = {
  ...WEAK, verdict: 'steady', verdict_label: '穩定', inflation: 1.0, yield_now: 0.05, yield_norm: 0.05,
  checks: WEAK.checks.map(c => ({ ...c, level: 'good', text: c.label + ' 正常。' })),
}
const NOT_ENOUGH = {
  enough: false, reason: '除息紀錄只有 3 次，至少需要 4 次才能判斷穩定度。', verdict: 'unknown', verdict_label: '資料不足',
  payouts: [], checks: [],
}

const FIX = {
  '0056': base('0056', '元大高股息', 'dividend', { health: WEAK }),
  '0050': base('0050', '元大台灣50', 'market', { health: STEADY }),
  '00999': base('00999', '新上市高息', 'dividend', { health: NOT_ENOUGH }),
  '009816': base('009816', '凱基台灣TOP50', 'market', { pays: false, health: { ...NOT_ENOUGH, reason: '近 5 年沒有除息紀錄。' } }),
}
const THRESHOLDS = {
  inflation: [1.1, 1.3], cv: [0.15, 0.35], trend: [0.9, 0.75], erosion: [0.3, 0.7],
  fill_weak_rate: 0.5, min_payouts: 4, recent_n: 8, principal_years: 3,
}

async function mockApi(page, { withThresholds = true, stripHealth = false } = {}) {
  await page.route('**/api/v1/etf-compare/chart**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { symbol: '0050', dates: [], open: [], high: [], low: [], close: [], volume: [], dividend_events: [], splits: [] } }) }))
  await page.route('**/api/v1/etf-compare/catalog', route =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          etfs: Object.values(FIX).map(f => ({ symbol: f.symbol, name: f.name, category: f.category })),
          presets: [{ key: 'health', label: '體檢情境', symbols: ['0050', '0056', '00999', '009816'] }],
          category_labels: { market: '市值型', dividend: '高股息', active: '主動型', other: '其他 ETF', stock: '個股' },
          max_symbols: 10, benchmark: '0050',
        },
      }),
    }))
  await page.route('**/api/v1/etf-compare/compare**', route => {
    const url = new URL(route.request().url())
    const syms = (url.searchParams.get('symbols') || '').split(',').filter(Boolean)
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          asof: '2026-10-30', symbols: syms.map(s => FIX[s]).filter(Boolean).map(({ health, ...rest }) => (stripHealth ? rest : { ...rest, health })), failed: [],
          event: { start: '2026-06-22', end: '2026-07-30', source: 'auto', drop: -0.15, anchor: '0050', lookback_days: 180 },
          method: { risk_free: 0.015, min_stats_days: 60, fill_window_days: 60, fill_lookback_years: 3, ...(withThresholds ? { health: THRESHOLDS } : {}) },
        },
      }),
    })
  })
  await page.route('**/api/v1/stocks/search**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) }))
}

test('配息體檢：總評、四項檢查、情境殖利率與最近配息', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')
  await page.getByRole('button', { name: '體檢情境' }).click()

  const section = page.locator('[data-section="div-health"]')
  await expect(section.getByRole('heading', { name: /配息體檢/ })).toBeVisible()

  const weak = section.locator('article[data-symbol="0056"]')
  await expect(weak).toHaveAttribute('data-verdict', 'weak')
  await expect(weak.getByTestId('health-verdict')).toContainText('偏弱')
  await expect(weak).toContainText('季配')
  await expect(weak).toContainText('8.0%') // 現價殖利率
  await expect(weak).toContainText('6.2%') // 常態殖利率
  await expect(weak).toContainText('1.30×') // 膨脹倍數

  // 四項檢查的等級（不單靠顏色：data-level 與圖示文字）
  await expect(weak.locator('[data-check="inflation"]')).toHaveAttribute('data-level', 'warn')
  await expect(weak.locator('[data-check="trend"]')).toHaveAttribute('data-level', 'bad')
  await expect(weak.locator('[data-check="trend"]')).toContainText('減少 60%')
  await expect(weak.locator('[data-check="principal"]')).toContainText('近 3.0 年價格 -30.0%')

  // 情境殖利率：保守、中性、最近一次年化
  const scen = weak.getByTestId('health-scenarios')
  await expect(scen).toContainText('保守')
  await expect(scen).toContainText('4.0%')
  await expect(scen).toContainText('中性')
  await expect(scen).toContainText('8.0%')

  // 最近 4 次配息的小長條
  await expect(weak.locator('.bar-wrap')).toHaveCount(4)

  const steady = section.locator('article[data-symbol="0050"]')
  await expect(steady).toHaveAttribute('data-verdict', 'steady')
  await expect(steady.getByTestId('health-verdict')).toContainText('穩定')
})

test('配息體檢：資料不足顯示原因、不配息的標的不出現', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')
  await page.getByRole('button', { name: '體檢情境' }).click()

  const section = page.locator('[data-section="div-health"]')
  const young = section.locator('article[data-symbol="00999"]')
  await expect(young).toHaveAttribute('data-verdict', 'unknown')
  await expect(young.getByTestId('health-reason')).toContainText('至少需要 4 次')
  await expect(young.locator('.kpis')).toHaveCount(0) // 不硬湊數字

  await expect(section.locator('article[data-symbol="009816"]')).toHaveCount(0)
})

test('配息體檢：判斷門檻說明的數字來自後端 method.health', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')
  await page.getByRole('button', { name: '體檢情境' }).click()

  const method = page.locator('[data-section="div-health"] details.method')
  await method.locator('summary').click()
  await expect(method).toContainText('> 1.10 留意、> 1.30 偏弱')
  await expect(method).toContainText('> 15% 留意、> 35% 偏弱')
  await expect(method).toContainText('< 0.90 留意、< 0.75 偏弱')
})

test('配息體檢：後端沒給 health（舊快取）時整頁不報錯、只顯示不適用', async ({ page }) => {
  // 模擬舊版後端／舊快取：回應裡完全沒有 health，也沒有 method.health
  await mockApi(page, { withThresholds: false, stripHealth: true })
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto('/etf-compare')
  await page.getByRole('button', { name: '體檢情境' }).click()

  await expect(page.getByTestId('div-health-empty')).toBeVisible()
  expect(errors).toEqual([])
})
