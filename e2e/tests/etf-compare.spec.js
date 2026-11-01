// @ts-check
const { test, expect } = require('@playwright/test')

// ETF 綜合比較頁。後端 API 全部 mock：這支測試驗證的是「前端怎麼呈現與重算」
// （含 1Y/YTD 的重新以 100 起算、不適用顯示「—」、事件區間參數），
// 數字本身的正確性由 backend/tests/test_etf_compare.py（含真實日線對帳）負責，
// 也避免 e2e 打 FinMind 把免費額度燒光。

function weekdays(from, to) {
  const out = []
  const d = new Date(`${from}T00:00:00Z`)
  const end = new Date(`${to}T00:00:00Z`)
  while (d <= end) {
    const wd = d.getUTCDay()
    if (wd !== 0 && wd !== 6) out.push(d.toISOString().slice(0, 10))
    d.setUTCDate(d.getUTCDate() + 1)
  }
  return out
}

const DATES = weekdays('2025-10-30', '2026-10-30')
function adjSeries(base, drift) {
  return DATES.map((_, i) => Number((base * Math.pow(1 + drift, i) * (1 + 0.01 * Math.sin(i / 7))).toFixed(4)))
}

function mk(symbol, name, category, o = {}) {
  const pays = o.pays !== false
  return {
    symbol, name, category,
    metrics: {
      first_date: o.first_date || '2021-05-03', history_days: 1300, last_close: 50, last_date: '2026-10-30',
      return_1y: o.ret1y ?? 0.663, cagr_3y: 'cagr3y' in o ? o.cagr3y : 0.548, ann_return: 0.663, ann_vol: 0.292,
      sharpe: o.sharpe ?? 1.92, mdd: -0.154, short_history: !!o.short, window_days: 242,
    },
    dividends: {
      pays_dividend: pays, yield_ttm: pays ? 0.0152 : null, ttm_amount: pays ? 1.6 : 0,
      by_year: [
        { year: 2024, amount: pays ? 1.0 : 0, yield: pays ? 0.02 : 0, count: pays ? 1 : 0, partial: false },
        { year: 2025, amount: pays ? 1.035 : 0, yield: pays ? 0.016 : 0, count: pays ? 1 : 0, partial: false },
        { year: 2026, amount: pays ? 1.6 : 0, yield: pays ? 0.015 : 0, count: pays ? 2 : 0, partial: true },
      ],
      events: [],
    },
    fill: pays
      ? { n: 6, filled: 6, failed: 0, pending: 0, avg_days: 3.0, success_rate: 1.0, events: [] }
      : { n: 0, filled: 0, failed: 0, pending: 0, avg_days: null, success_rate: null, events: [] },
    scores: {
      return: 100, defense: 95, sharpe: 100, yield: pays ? 15.2 : null, fill: pays ? 98 : null,
      total: o.total ?? 81.6, return_basis: 'cagr_3y',
    },
    series: { dates: DATES, adj: adjSeries(o.base ?? 100, o.drift ?? 0.0015) },
    splits: [],
    event: {
      high: 112.3, high_date: '2026-06-23', low: 91.8, low_date: '2026-07-29', drawdown: -0.1825,
      rebound_high: 116.6, rebound_date: '2026-10-06', rebound_pct: 0.2701, dividends_in_window: pays ? 0.6 : 0, partial: false,
    },
  }
}

const FIX = {
  '0050': mk('0050', '元大台灣50', 'market', { total: 81.6 }),
  '0056': mk('0056', '元大高股息', 'dividend', { total: 92.2, drift: 0.0012 }),
  '00981A': mk('00981A', '主動統一台股增長', 'active', { total: 83.6, cagr3y: null, short: true, first_date: '2025-05-27', drift: 0.002 }),
  '009816': mk('009816', '凱基台灣TOP50', 'market', { total: 70.0, pays: false, drift: 0.001 }),
}

const CATALOG = {
  success: true,
  data: {
    etfs: [
      { symbol: '0050', name: '元大台灣50', category: 'market' },
      { symbol: '0056', name: '元大高股息', category: 'dividend' },
      { symbol: '00981A', name: '主動統一台股增長', category: 'active' },
      { symbol: '009816', name: '凱基台灣TOP50', category: 'market' },
    ],
    presets: [{ key: 'cap_vs_div', label: '市值 vs 高股息', symbols: ['0050', '0056', '00981A', '009816'] }],
    category_labels: { market: '市值型', dividend: '高股息', active: '主動型', other: '其他 ETF', stock: '個股' },
    max_symbols: 10,
    benchmark: '0050',
  },
}

/** @param {import('@playwright/test').Page} page */
async function mockApi(page, calls = []) {
  await page.route('**/api/v1/etf-compare/catalog', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CATALOG) }))
  await page.route('**/api/v1/etf-compare/compare**', route => {
    const url = new URL(route.request().url())
    calls.push(url)
    const syms = (url.searchParams.get('symbols') || '').split(',').filter(Boolean)
    const symbols = []
    const failed = []
    for (const s of syms) {
      if (FIX[s]) symbols.push(FIX[s])
      else if (s.startsWith('9999')) failed.push({ symbol: s, name: '', reason: '查無日線資料（代碼錯誤或尚未上市）' })
      else symbols.push({ ...FIX['0050'], symbol: s, name: `測試${s}`, category: 'other' })
    }
    const es = url.searchParams.get('event_start')
    const event = es
      ? { start: es, end: url.searchParams.get('event_end'), source: 'custom', drop: null }
      : { start: '2026-06-22', end: '2026-07-30', source: 'auto', drop: -0.1537 }
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          asof: '2026-10-30', symbols, failed, event,
          method: { risk_free: 0.015, min_stats_days: 60, fill_window_days: 60, fill_lookback_years: 3 },
        },
      }),
    })
  })
  await page.route('**/api/v1/stocks/search**', route =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: '2330', name_zh: '台積電' }] } }),
    }))
}

test('一鍵情境載入：五張圖表與各表格依資料呈現', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')

  await page.getByRole('button', { name: '市值 vs 高股息' }).click()

  const rows = page.locator('[data-testid="score-table"] tbody tr')
  await expect(rows).toHaveCount(4)
  // 依總分由高到低排序：0056 (92.2) 在最前
  await expect(rows.first()).toContainText('0056')
  await expect(page.locator('[data-section="radar"] svg.radar')).toBeVisible()

  // 績效表
  const perf = page.locator('[data-testid="perf-table"] tbody tr[data-symbol="0050"]')
  await expect(perf).toContainText('+66.3%')
  await expect(perf).toContainText('-15.4%')
  await expect(perf).toContainText('1.92')

  // 上市未滿一年：3 年年化顯示「—」並標示徽章
  const young = page.locator('[data-testid="perf-table"] tbody tr[data-symbol="00981A"]')
  await expect(young).toContainText('上市未滿1年')
  await expect(young.locator('td').nth(2)).toHaveText('—')

  // 不配息：殖利率與填息分數顯示「—」而不是 0，配息表有說明
  const nonPayer = page.locator('[data-testid="score-table"] tbody tr[data-symbol="009816"]')
  await expect(nonPayer.locator('td').nth(5)).toHaveText('—')
  await expect(nonPayer.locator('td').nth(6)).toHaveText('—')
  // 只平均 3 項的總分要標出項數，避免與滿 5 項的總分被誤認為同一把尺
  await expect(nonPayer.locator('.axes-n')).toContainText('3項')
  await expect(page.locator('[data-testid="score-table"] tbody tr[data-symbol="0050"] .axes-n')).toHaveCount(0)
  await expect(page.locator('[data-testid="div-table"] tr[data-symbol="009816"]')).toContainText('沒有除息紀錄')

  // 急跌與反彈
  await expect(page.locator('[data-testid="event-desc"]')).toContainText('2026-06-22')
  await expect(page.locator('[data-testid="event-desc"]')).toContainText('自動偵測')
  const ev = page.locator('[data-testid="event-table"] tr[data-symbol="0050"]')
  await expect(ev).toContainText('91.80')
  await expect(ev).toContainText('+27.0%')

  // 持股明細：誠實說明沒有資料，不放假數字
  await expect(page.locator('[data-testid="holdings-note"]')).toContainText('不會用手寫的數字充數')

  // 網址帶上選擇，方便分享
  await expect(page).toHaveURL(/symbols=0050%2C0056%2C00981A%2C009816|symbols=0050,0056,00981A,009816/)
})

test('搜尋加入標的：變更後提示更新，送出的請求帶正確代碼', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  await page.goto('/etf-compare')

  await page.getByTestId('etf-search').fill('0056')
  await page.getByRole('option', { name: /0056/ }).click()
  await expect(page.locator('.chip[data-symbol="0056"]')).toBeVisible()
  await expect(page.locator('.dirty')).toContainText('選擇已變更')

  await page.getByTestId('etf-run').click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(1)
  expect(calls.at(-1).searchParams.get('symbols')).toBe('0056')
  await expect(page.locator('.dirty')).toHaveCount(0)

  // 再加一檔 → 又出現提示、按鈕改為「更新比較」
  await page.getByTestId('etf-search').fill('0050')
  await page.getByRole('option', { name: /0050/ }).click()
  await expect(page.locator('.dirty')).toBeVisible()
  await expect(page.getByTestId('etf-run')).toContainText('更新比較')
  await page.getByTestId('etf-run').click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(2)
  expect(calls.at(-1).searchParams.get('symbols')).toBe('0056,0050')
})

test('搜尋框也能找個股（經由股票搜尋 API）', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')
  await page.getByTestId('etf-search').fill('台積')
  await page.getByRole('option', { name: /2330/ }).click()
  await expect(page.locator('.chip[data-symbol="2330"]')).toContainText('台積電')
})

test('走勢區間切換：依區間重新以 100 起算並與日資料吻合', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050')
  await expect(page.locator('[data-testid="trend-chart"] canvas').first()).toBeVisible()

  const adj = FIX['0050'].series.adj
  const dates = FIX['0050'].series.dates
  const last = adj[adj.length - 1]
  const expect1y = `${((last / adj[0] - 1) * 100) >= 0 ? '+' : ''}${((last / adj[0] - 1) * 100).toFixed(1)}%`
  const ytdBase = adj[dates.findIndex(d => d >= '2026-01-01')]
  const expectYtd = `+${((last / ytdBase - 1) * 100).toFixed(1)}%`

  const legend = page.locator('[data-section="trend"] .legend-item').first()
  await expect(legend).toContainText(expect1y)
  await page.getByRole('tab', { name: 'YTD' }).click()
  await expect(legend).toContainText(expectYtd)
  await page.getByRole('tab', { name: '6M' }).click()
  await expect(legend).not.toContainText(expectYtd)
})

test('自訂急跌區間：請求帶日期參數，可回到自動偵測', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.locator('[data-testid="event-desc"]')).toContainText('自動偵測')

  await page.locator('.event-form input[type="date"]').first().fill('2026-03-02')
  await page.locator('.event-form input[type="date"]').nth(1).fill('2026-04-10')
  await page.getByRole('button', { name: '套用區間' }).click()

  await expect(page.locator('[data-testid="event-desc"]')).toContainText('自訂區間')
  const c = calls.at(-1)
  expect(c.searchParams.get('event_start')).toBe('2026-03-02')
  expect(c.searchParams.get('event_end')).toBe('2026-04-10')

  await page.getByRole('button', { name: '回到自動偵測' }).click()
  await expect(page.locator('[data-testid="event-desc"]')).toContainText('自動偵測')
  expect(calls.at(-1).searchParams.has('event_start')).toBe(false)
})

test('上限 10 檔：滿了就停用搜尋框，移除後恢復', async ({ page }) => {
  await mockApi(page)
  const ten = ['0050', '0056', '00981A', '009816', '1101', '1102', '1216', '2002', '2317', '2412'].join(',')
  await page.goto(`/etf-compare?symbols=${ten}`)
  await expect(page.locator('.chip')).toHaveCount(10)
  await expect(page.getByTestId('etf-search')).toBeDisabled()
  await page.getByRole('button', { name: '移除 2412' }).click()
  await expect(page.locator('.chip')).toHaveCount(9)
  await expect(page.getByTestId('etf-search')).toBeEnabled()
})

test('查無資料的標的只提示、不影響其他標的；全數失敗顯示錯誤', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,9999X')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(1)
  await expect(page.locator('.asof')).toContainText('查無資料：9999X')

  // 全數失敗（後端 502）
  await page.route('**/api/v1/etf-compare/compare**', route =>
    route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify({ detail: '所選標的都查不到日線資料，請稍後再試。' }) }))
  await page.getByTestId('etf-search').fill('0056')
  await page.getByRole('option', { name: /0056/ }).click()
  await page.getByTestId('etf-run').click()
  await expect(page.getByRole('alert')).toContainText('都查不到日線資料')
})

test('Ctrl+K 與側邊欄都能到 ETF 比較頁', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await expect(page.locator('aside a[href="/etf-compare"]').first()).toBeVisible()

  await page.keyboard.press('Control+k')
  await page.locator('.qs-input').fill('etf')
  await expect(page.locator('.qs-panel .qs-item').first()).toContainText('ETF 綜合比較')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/etf-compare/)
})

test('匯出 CSV 下載一份含每檔指標的檔案', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(2)
  const [dl] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /匯出 CSV/ }).click(),
  ])
  expect(dl.suggestedFilename()).toMatch(/^etf-compare-\d{4}-\d{2}-\d{2}\.csv$/)
})

test('手機寬度：整頁不出現橫向捲動', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056,00981A,009816')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})
