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

// 走勢圖（/chart）用的合成日線：可手算——收盤＝基準＋三角波＋緩升，開盤＝前一日收盤，量有規律。
// 測試端自己用這份陣列算 MA／KD，與畫面圖例對帳。
function chartSeries(symbol) {
  const shift = symbol === '0056' ? 10 : 0
  const close = DATES.map((_, i) => Number((100 + shift + (i % 20) * 0.5 + i * 0.02).toFixed(2)))
  const open = close.map((c, i) => (i ? close[i - 1] : Number((c - 0.3).toFixed(2))))
  const high = close.map((c, i) => Number((Math.max(c, open[i]) + 0.5).toFixed(2)))
  const low = close.map((c, i) => Number((Math.min(c, open[i]) - 0.5).toFixed(2)))
  const volume = close.map((_, i) => 40000 + (i % 7) * 1000)
  return { dates: DATES, open, high, low, close, volume }
}
const chartBody = symbol => JSON.stringify({
  success: true,
  data: { symbol, ...chartSeries(symbol), dividend_events: [{ date: '2026-01-20', amount: 0.5 }, { date: '2026-07-21', amount: 0.6 }], splits: [] },
})
const avg = (arr, end, n) => arr.slice(end - n + 1, end + 1).reduce((a, b) => a + b, 0) / n
// 測試端自己算一次 KD（9,3,3，起始 50），不借用前端的實作
function refKd(s) {
  let k = 50, d = 50
  const out = []
  for (let i = 8; i < s.close.length; i++) {
    const hh = Math.max(...s.high.slice(i - 8, i + 1))
    const ll = Math.min(...s.low.slice(i - 8, i + 1))
    const rsv = hh > ll ? ((s.close[i] - ll) / (hh - ll)) * 100 : 50
    k = (2 / 3) * k + (1 / 3) * rsv
    d = (2 / 3) * d + (1 / 3) * k
    out[i] = { rsv, k, d, j9: 3 * d - 2 * k, k3d2: 3 * k - 2 * d }
  }
  return out
}

function mk(symbol, name, category, o = {}) {
  const pays = o.pays !== false
  return {
    symbol, name, category,
    metrics: {
      first_date: o.first_date || '2021-05-03', history_days: 1300, last_close: o.last_close ?? 100, last_date: '2026-10-30',
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
      events: o.events || [],
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
      window_low: 88.4, window_low_date: '2026-06-24', // 低點出現在最高點之前：區間最低 ≠ 其後最低
      rebound_high: 116.6, rebound_date: '2026-10-06', rebound_pct: 0.2701, dividends_in_window: pays ? 0.6 : 0, partial: false,
      ...(o.event || {}),
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
async function mockApi(page, calls = [], override = {}, chartCalls = []) {
  // 走勢圖資料一律 mock：不然急跌表下面的走勢圖會去打真的後端／FinMind
  await page.route('**/api/v1/etf-compare/chart**', route => {
    const url = new URL(route.request().url())
    chartCalls.push(url)
    route.fulfill({ status: 200, contentType: 'application/json', body: chartBody(url.searchParams.get('symbol')) })
  })
  await page.route('**/api/v1/etf-compare/catalog', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CATALOG) }))
  await page.route('**/api/v1/etf-compare/compare**', route => {
    const url = new URL(route.request().url())
    calls.push(url)
    const syms = (url.searchParams.get('symbols') || '').split(',').filter(Boolean)
    const symbols = []
    const failed = []
    for (const s of syms) {
      if (override[s]) symbols.push(override[s])
      else if (FIX[s]) symbols.push(FIX[s])
      else if (s.startsWith('9999')) failed.push({ symbol: s, name: '', reason: '查無日線資料（代碼錯誤或尚未上市）' })
      else symbols.push({ ...FIX['0050'], symbol: s, name: `測試${s}`, category: 'other' })
    }
    const es = url.searchParams.get('event_start')
    const event = es
      ? { start: es, end: url.searchParams.get('event_end'), source: 'custom', drop: null }
      : {
        start: '2026-06-22', end: '2026-07-30', source: 'auto', drop: -0.1537,
        anchor: url.searchParams.get('auto_anchor') || '0050', lookback_days: Number(url.searchParams.get('auto_lookback') || 180),
      }
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
  await page.locator('.search-dropdown').getByRole('option', { name: /0056/ }).click()
  await expect(page.locator('.chip[data-symbol="0056"]')).toBeVisible()
  await expect(page.locator('.dirty')).toContainText('選擇已變更')

  await page.getByTestId('etf-run').click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(1)
  expect(calls.at(-1).searchParams.get('symbols')).toBe('0056')
  await expect(page.locator('.dirty')).toHaveCount(0)

  // 再加一檔 → 又出現提示、按鈕改為「更新比較」
  await page.getByTestId('etf-search').fill('0050')
  await page.locator('.search-dropdown').getByRole('option', { name: /0050/ }).click()
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
  await page.locator('.search-dropdown').getByRole('option', { name: /2330/ }).click()
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
  await page.locator('.search-dropdown').getByRole('option', { name: /0056/ }).click()
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

// ── 品管回報後的改善：圖例開關、急跌表說明、我的組合、調整順序、觀察清單 ──────────

test('走勢圖例：點一下開關單條線、連點兩下只看一條，切換區間後仍保持', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056,00981A,009816')
  const chart = page.getByTestId('trend-chart')
  await expect(chart.locator('canvas').first()).toBeVisible()
  await expect(chart).toHaveAttribute('data-visible', '0050,0056,00981A,009816')

  const legend = sym => page.locator(`[data-section="trend"] .legend-btn[data-symbol="${sym}"]`)
  await legend('0056').click()
  await expect(legend('0056')).toHaveAttribute('aria-pressed', 'false')
  await expect(legend('0056')).toHaveClass(/off/)
  await expect(chart).toHaveAttribute('data-visible', '0050,00981A,009816')

  // 切換區間會重畫圖表，被關掉的線要維持關閉
  await page.getByRole('tab', { name: '6M' }).click()
  await expect(chart).toHaveAttribute('data-visible', '0050,00981A,009816')
  await expect(legend('0056')).toHaveClass(/off/)

  await legend('0056').click()
  await expect(chart).toHaveAttribute('data-visible', '0050,0056,00981A,009816')

  // 連點兩下 → 只看這一條；再連點兩下 → 回到全部顯示
  await legend('00981A').dblclick()
  await expect(chart).toHaveAttribute('data-visible', '00981A')
  await legend('00981A').dblclick()
  await expect(chart).toHaveAttribute('data-visible', '0050,0056,00981A,009816')

  await page.getByTestId('series-hide-all').click()
  await expect(chart).toHaveAttribute('data-visible', '')
  await page.getByTestId('series-show-all').click()
  await expect(chart).toHaveAttribute('data-visible', '0050,0056,00981A,009816')

  await page.getByTestId('chart-reset').click()
  await expect(chart.locator('canvas').first()).toBeVisible()
})

test('急跌表：沒反彈、沒除息、沒配息各自有說明，不再是一個看不懂的「—」', async ({ page }) => {
  const override = {
    // 最低點就是最新交易日：之後沒有資料，算不出反彈
    '0056': mk('0056', '元大高股息', 'dividend', {
      total: 92.2, last_close: 50,
      events: [{ date: '2026-06-16', amount: 0.5 }, { date: '2026-09-16', amount: 0.6 }],
      event: { low: 48, low_date: '2026-10-30', rebound_high: null, rebound_date: null, rebound_pct: null, dividends_in_window: 0 },
    }),
  }
  await mockApi(page, [], override)
  await page.goto('/etf-compare?symbols=0050,0056,009816')
  const row = sym => page.locator(`[data-testid="event-table"] tr[data-symbol="${sym}"]`)

  await expect(row('0056').getByTestId('no-rebound')).toContainText('尚未反彈')
  await expect(row('0056').getByTestId('no-rebound')).toContainText('最低點就是最新交易日 10/30')
  await expect(row('0056').getByTestId('from-low')).toHaveText('+4.2%')
  await expect(row('0056').getByTestId('no-div')).toHaveText('無除息')
  await expect(row('0056')).toContainText('前次 06/16・下次 09/16')
  await expect(row('0056')).not.toContainText('—')

  // 有反彈、有除息的照常顯示數字
  await expect(row('0050')).toContainText('+27.0%')
  await expect(row('0050')).toContainText('0.60 元')
  await expect(row('0050').getByTestId('from-low')).toHaveText('+8.9%')

  // 從不配息的 ETF 寫「尚未配息」，不是「無除息」
  await expect(row('009816').getByTestId('no-div')).toHaveText('尚未配息')
})

test('我的組合：存起來、重新整理後還在、一鍵載入、同名更新、刪除', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  await page.goto('/etf-compare')
  await page.getByRole('button', { name: '市值 vs 高股息' }).click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)

  await page.getByTestId('portfolio-name').fill('核心四檔')
  await page.getByTestId('portfolio-save').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('已存成組合「核心四檔」')
  await expect(page.locator('[data-portfolio="核心四檔"]')).toContainText('4 檔')

  // 存在本機瀏覽器：重新整理仍在；重設後點它能一鍵載入同一組
  await page.reload()
  await expect(page.locator('[data-portfolio="核心四檔"]')).toBeVisible()
  await page.getByRole('button', { name: '重設', exact: true }).click()
  await expect(page.locator('.chip')).toHaveCount(0)
  await page.locator('[data-portfolio="核心四檔"] .pf-load').click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  expect(calls.at(-1).searchParams.get('symbols')).toBe('0050,0056,00981A,009816')

  // 同名再存 = 更新內容
  await page.getByRole('button', { name: '移除 009816' }).click()
  await page.getByTestId('portfolio-name').fill('核心四檔')
  await page.getByTestId('portfolio-save').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('已更新組合「核心四檔」（3 檔）')
  await expect(page.locator('[data-portfolio]')).toHaveCount(1)
  await expect(page.locator('[data-portfolio="核心四檔"]')).toContainText('3 檔')

  // 刪除（有確認）
  page.once('dialog', d => d.accept())
  await page.getByRole('button', { name: '刪除組合 核心四檔' }).click()
  await expect(page.locator('[data-portfolio]')).toHaveCount(0)
  await page.reload()
  await expect(page.locator('[data-portfolio]')).toHaveCount(0)
})

test('調整順序：◀ ▶ 與拖曳都會改圖例、表格與網址，且不用重打 API', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  await page.goto('/etf-compare?symbols=0050,0056,00981A,009816')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  const before = calls.length

  const perfOrder = () => page.locator('[data-testid="perf-table"] tbody tr').evaluateAll(trs => trs.map(t => t.dataset.symbol))
  const legendOrder = () => page.locator('[data-section="trend"] .legend-btn').evaluateAll(bs => bs.map(b => b.dataset.symbol))
  expect(await perfOrder()).toEqual(['0050', '0056', '00981A', '009816'])

  await page.getByRole('button', { name: '0056 往前移' }).click()
  await expect.poll(perfOrder).toEqual(['0056', '0050', '00981A', '009816'])
  await expect.poll(legendOrder).toEqual(['0056', '0050', '00981A', '009816'])
  await expect(page).toHaveURL(/symbols=0056(%2C|,)0050/)
  await expect(page.locator('.dirty')).toHaveCount(0)
  // 第一個不能再往前、最後一個不能再往後
  await expect(page.getByRole('button', { name: '0056 往前移' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '009816 往後移' })).toBeDisabled()

  // 拖曳：把 009816 拖到最前面
  await page.locator('.chip[data-symbol="009816"]').dragTo(page.locator('.chip[data-symbol="0056"]'))
  await expect.poll(perfOrder).toEqual(['009816', '0056', '0050', '00981A'])

  // 只是排序，沒有重新請求
  expect(calls.length).toBe(before)
  await expect(page.locator('[data-testid="chip-row"] .chip').first()).toHaveAttribute('data-symbol', '009816')
})

test('觀察清單：匯入只補進比較清單、全部加入只新增不覆蓋', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')

  // 觀察清單是空的
  await page.getByTestId('import-watchlist').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('觀察清單是空的')

  await page.evaluate(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['2330', '0050'])))
  await page.getByTestId('import-watchlist').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('已從觀察清單加入 2 檔')
  await expect(page.locator('.chip')).toHaveCount(2)
  await page.getByTestId('import-watchlist').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('都已經在比較清單裡')

  // 全部加入觀察清單：只新增沒有的，原有的 2330、0050 保留
  await page.getByRole('button', { name: '市值 vs 高股息' }).click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  await page.getByTestId('push-watchlist').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('已把 3 檔加入觀察清單（原有的 2 檔不受影響）')
  const wl = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist')))
  expect(wl).toEqual(['0056', '00981A', '009816', '2330', '0050'])
  await page.getByTestId('push-watchlist').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('都已經在觀察清單裡')
})

// ── 品管第二輪回報 ──────────────────────────────────────────────────────────

test('急跌表新增「區間最低」與「目前價位」，且區間最低可以比「其後最低」更低', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056')
  const row = sym => page.locator(`[data-testid="event-table"] tr[data-symbol="${sym}"]`)

  // 品管 11/03：「目前價位」放在「目前價距低點」的前面（反彈幅度之後）
  const headCells = page.locator('[data-testid="event-table"] thead th')
  const heads = ['標的', '區間最低', '區間最高', '其後最低', '回落', '反彈高點', '反彈幅度', '目前價位', '目前價距低點', '區間內除息']
  await expect(headCells).toHaveText(heads) // 會等表格畫出來（allInnerTexts 不會等）

  // 區間最低 88.40（6/24，在高點之前）；其後最低 91.80（7/29）；目前價位 = 最新收盤 100.00（10/30）
  await expect(row('0050').getByTestId('window-low')).toContainText('88.40')
  await expect(row('0050').getByTestId('window-low')).toContainText('06/24')
  await expect(row('0050')).toContainText('91.80')
  await expect(row('0050').getByTestId('last-price')).toContainText('100.00')
  await expect(row('0050').getByTestId('last-price')).toContainText('10/30')

  // 資料列的格子順序跟表頭一致：目前價位緊接在反彈幅度之後、目前價距低點之前
  const cells = await row('0050').locator('td').allInnerTexts()
  expect(cells).toHaveLength(heads.length)
  expect(cells[6]).toContain('+27.0%')
  expect(cells[7]).toContain('100.00')
  expect(cells[8]).toContain('+8.9%')
})

test('急跌表：尚未反彈的列，目前價位仍然在目前價距低點前面，欄數不跑掉', async ({ page }) => {
  const override = {
    '0056': mk('0056', '元大高股息', 'dividend', {
      total: 92.2, last_close: 50,
      event: { low: 48, low_date: '2026-10-30', rebound_high: null, rebound_date: null, rebound_pct: null, dividends_in_window: 0 },
    }),
  }
  await mockApi(page, [], override)
  await page.goto('/etf-compare?symbols=0050,0056')
  const cells = page.locator('[data-testid="event-table"] tr[data-symbol="0056"] td')
  // 標的、區間最低、區間最高、其後最低、回落、〔尚未反彈 ×2 欄〕、目前價位、目前價距低點、區間內除息
  await expect(cells).toHaveCount(9)
  await expect(cells.nth(5)).toContainText('尚未反彈')
  await expect(cells.nth(6)).toContainText('50.00')
  await expect(cells.nth(7)).toContainText('+4.2%')
})

test('自動偵測可設定基準與回看期間：維持自動模式，請求帶參數、說明文字跟著變', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('auto-settings')).toBeVisible()
  await expect(page.getByTestId('event-desc')).toContainText('0050 近 180 天最大回落')
  expect(calls.at(-1).searchParams.get('auto_anchor')).toBe('0050')
  expect(calls.at(-1).searchParams.get('auto_lookback')).toBe('180')

  await page.getByTestId('auto-lookback').selectOption('365')
  await expect(page.getByTestId('event-desc')).toContainText('近 1 年最大回落')
  expect(calls.at(-1).searchParams.get('auto_lookback')).toBe('365')

  await page.getByTestId('auto-anchor').selectOption('0056')
  await expect(page.getByTestId('event-desc')).toContainText('0056 近 1 年最大回落')
  expect(calls.at(-1).searchParams.get('auto_anchor')).toBe('0056')
  expect(calls.at(-1).searchParams.has('event_start')).toBe(false) // 還是自動偵測，沒變成自訂區間
  await expect(page.getByTestId('event-desc')).toContainText('自動偵測')

  // 基準那一檔被移除 → 選單退回 0050，不會送出後端會拒絕的參數
  await page.getByRole('button', { name: '移除 0056' }).click()
  await expect(page.getByTestId('auto-anchor')).toHaveValue('0050')
  await page.getByTestId('etf-run').click()
  await expect.poll(() => calls.at(-1).searchParams.get('auto_anchor')).toBe('0050')

  // 自訂區間時不顯示偵測設定；回到自動後設定還在
  await page.locator('[data-quick="6m"]').click()
  await expect(page.getByTestId('auto-settings')).toHaveCount(0)
  await page.getByRole('button', { name: '回到自動偵測' }).click()
  await expect(page.getByTestId('auto-settings')).toBeVisible()
  await expect(page.getByTestId('auto-lookback')).toHaveValue('365')
})

test('快速區間：一鍵套用成以最新資料日往回推的自訂區間', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  await page.goto('/etf-compare?symbols=0050')
  await expect(page.getByTestId('event-desc')).toContainText('自動偵測')

  await page.locator('[data-quick="3m"]').click()
  await expect(page.getByTestId('event-desc')).toContainText('自訂區間')
  let c = calls.at(-1)
  expect(c.searchParams.get('event_start')).toBe('2026-07-30')
  expect(c.searchParams.get('event_end')).toBe('2026-10-30')
  await expect(page.locator('.event-form input[type="date"]').first()).toHaveValue('2026-07-30')

  await page.locator('[data-quick="ytd"]').click()
  c = calls.at(-1)
  expect(c.searchParams.get('event_start')).toBe('2026-01-01')
  expect(c.searchParams.get('event_end')).toBe('2026-10-30')

  await page.locator('[data-quick="1y"]').click()
  expect(calls.at(-1).searchParams.get('event_start')).toBe('2025-10-30')
})

test('被限流：保留畫面上已有的結果、顯示倒數，時間到自動重試；標的清單不必重新取得', async ({ page }) => {
  const calls = []
  await mockApi(page, calls)
  let catalogHits = 0
  await page.route('**/api/v1/etf-compare/catalog', route => {
    catalogHits++
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CATALOG) })
  })
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(2)
  expect(catalogHits).toBe(1)

  // 重新整理：清單來自瀏覽器快取，不再打 /catalog（少一次請求，也不會再出現「ETF 清單暫時無法載入」）
  await page.reload()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(2)
  expect(catalogHits).toBe(1)
  await expect(page.getByRole('button', { name: '市值 vs 高股息' })).toBeVisible()

  // 接下來的查詢被限流（附 Retry-After），之後恢復
  let limited = 0
  await page.route('**/api/v1/etf-compare/compare**', route => {
    if (limited++ === 0) {
      route.fulfill({
        status: 429, contentType: 'application/json', headers: { 'Retry-After': '5' },
        body: JSON.stringify({ detail: '查詢過於頻繁，請約 1 分鐘後再試。' }),
      })
    } else {
      route.fallback()
    }
  })
  await page.getByTestId('etf-search').fill('00981A')
  await page.locator('.search-dropdown').getByRole('option', { name: /00981A/ }).click()
  await page.getByTestId('etf-run').click()

  await expect(page.locator('.error-text')).toContainText('查詢過於頻繁')
  await expect(page.getByTestId('rate-limit-note')).toContainText('畫面上已有的結果會保留')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(2) // 舊結果沒被清掉

  // 倒數結束自動重試 → 三檔結果出現、提示消失
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(3, { timeout: 15_000 })
  await expect(page.getByTestId('rate-limit-note')).toHaveCount(0)
  await expect(page.locator('.error-text')).toHaveCount(0)
})

test('五維評分可像走勢圖一樣開關線：點一下開關、連點兩下只看一檔、全部顯示／隱藏', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056,00981A,009816')
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  const svg = page.locator('[data-section="radar"] svg.radar')
  const polys = page.locator('[data-section="radar"] svg.radar g.poly')
  const toggle = sym => page.locator(`[data-testid="radar-toggle"][data-symbol="${sym}"]`)
  await expect(polys).toHaveCount(4)

  await toggle('0056').click()
  await expect(polys).toHaveCount(3)
  await expect(svg).not.toHaveAttribute('data-visible', /0056/)
  await expect(toggle('0056')).toHaveAttribute('aria-pressed', 'false')
  // 表格資料與排名都還在，只是該列變淡
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  await expect(page.locator('[data-testid="score-table"] tbody tr[data-symbol="0056"]')).toHaveClass(/radar-off/)
  await toggle('0056').click()
  await expect(polys).toHaveCount(4)

  // 連點兩下 = 只看這一檔；再連點兩下回到全部
  await toggle('0050').dblclick()
  await expect(polys).toHaveCount(1)
  await expect(svg).toHaveAttribute('data-visible', '0050')
  await toggle('0050').dblclick()
  await expect(polys).toHaveCount(4)

  await page.getByTestId('radar-hide-all').click()
  await expect(polys).toHaveCount(0)
  await expect(page.getByTestId('radar-empty')).toBeVisible()
  await page.getByTestId('radar-show-all').click()
  await expect(polys).toHaveCount(4)
  await expect(page.getByTestId('radar-empty')).toHaveCount(0)

  // 雷達圖的開關不影響走勢圖
  await toggle('0050').click()
  await expect(page.getByTestId('trend-chart')).toHaveAttribute('data-visible', /0050/)
})

test('我的組合：載入後刪減，一鍵「更新這個組合」；另存新組合與同名覆蓋都有提示', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare')
  await page.getByRole('button', { name: '市值 vs 高股息' }).click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  await page.getByTestId('portfolio-name').fill('核心四檔')
  await page.getByTestId('portfolio-save').click()
  await expect(page.locator('[data-portfolio="核心四檔"]')).toContainText('4 檔')

  // 重設後載入：知道「目前是哪一組」，名稱欄預填，內容相同時不能更新
  await page.getByRole('button', { name: '重設', exact: true }).click()
  await page.locator('[data-portfolio="核心四檔"] .pf-load').click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(4)
  await expect(page.getByTestId('portfolio-state')).toContainText('核心四檔')
  await expect(page.getByTestId('portfolio-state')).toHaveAttribute('data-dirty', '0')
  await expect(page.getByTestId('portfolio-name')).toHaveValue('核心四檔')
  await expect(page.getByTestId('portfolio-update')).toBeDisabled()

  // 刪掉兩檔 → 出現「已修改、尚未儲存」，組合標籤也標示；按更新比較套用後仍是未儲存
  await page.getByRole('button', { name: '移除 009816' }).click()
  await page.getByRole('button', { name: '移除 00981A' }).click()
  await expect(page.getByTestId('portfolio-state')).toContainText('已修改、尚未儲存（已存 4 檔 → 現在 2 檔）')
  await expect(page.locator('[data-portfolio="核心四檔"]').getByTestId('pf-unsaved')).toBeVisible()
  await page.getByTestId('etf-run').click()
  await expect(page.locator('[data-testid="score-table"] tbody tr')).toHaveCount(2)
  await expect(page.getByTestId('portfolio-update')).toBeEnabled()

  // 一鍵更新：不必重打名稱
  await page.getByTestId('portfolio-update').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('已更新組合「核心四檔」：4 檔 → 2 檔')
  await expect(page.locator('[data-portfolio="核心四檔"]')).toContainText('2 檔')
  await expect(page.getByTestId('portfolio-state')).toHaveAttribute('data-dirty', '0')
  await expect(page.getByTestId('pf-unsaved')).toHaveCount(0)
  await expect(page.getByTestId('portfolio-update')).toBeDisabled()

  // 重新整理後仍記得是這一組；再調順序也算已修改
  await page.reload()
  await expect(page.getByTestId('portfolio-state')).toContainText('核心四檔')
  await expect(page.getByTestId('portfolio-state')).toHaveAttribute('data-dirty', '0')
  await page.getByRole('button', { name: '0056 往前移' }).click()
  await expect(page.getByTestId('portfolio-state')).toHaveAttribute('data-dirty', '1')
  await page.getByRole('button', { name: '0050 往前移' }).click() // 換回原順序 → 不再是已修改
  await expect(page.getByTestId('portfolio-state')).toHaveAttribute('data-dirty', '0')

  // 另存新組合：改個名字，原本那組不受影響
  await page.getByRole('button', { name: '0056 往前移' }).click()
  await expect(page.getByTestId('portfolio-save')).toHaveText('覆蓋同名組合') // 名稱欄還是舊名字
  await page.getByTestId('portfolio-name').fill('調過順序')
  await expect(page.getByTestId('portfolio-save')).toHaveText('另存新組合')
  await page.getByTestId('portfolio-save').click()
  await expect(page.getByTestId('portfolio-msg')).toContainText('已存成組合「調過順序」（2 檔）')
  await expect(page.locator('[data-portfolio]')).toHaveCount(2)
  await expect(page.locator('[data-portfolio="核心四檔"]')).toContainText('2 檔')

  // 輸入別組的名字 → 事先提醒會覆蓋；名稱空白時有說明，按鈕停用
  await page.getByTestId('portfolio-name').fill('核心四檔')
  await expect(page.getByTestId('name-clash')).toContainText('已有同名組合「核心四檔」')
  await page.getByTestId('portfolio-name').fill('')
  await expect(page.getByTestId('name-hint')).toBeVisible()
  await expect(page.getByTestId('portfolio-save')).toBeDisabled()
})

// ── 品管 11/02、11/03：急跌與反彈的個股走勢圖 ─────────────────────────────────────
// canvas 的內容不做像素比對；圖例、頂部資訊列與「圖上標註」清單都是 DOM，數字拿測試端自己算的值對帳。

const chartPanel = page => page.getByTestId('event-chart-panel')
const f2 = x => x.toFixed(2)
const numOf = async loc => Number((await loc.innerText()).replace(/,/g, ''))
// 圖例是 2 位小數的四捨五入，與測試端的直接加總在剛好對半時可能差 0.01，所以用容許誤差比
const expectNear = async (loc, want) => {
  await expect.poll(async () => Math.abs((await numOf(loc)) - want)).toBeLessThan(0.011)
}

test('急跌與反彈：表格下方有個股走勢圖，預設第一檔，頂部是最新一日的開高低收量與漲跌', async ({ page }) => {
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  const chartCalls = []
  await mockApi(page, [], {}, chartCalls)
  await page.goto('/etf-compare?symbols=0050,0056')

  await expect(chartPanel(page)).toBeVisible()
  await expect(page.getByTestId('chart-chip-0050')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('chart-chip-0056')).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  expect(chartCalls.map(u => u.searchParams.get('symbol'))).toEqual(['0050'])

  const s = chartSeries('0050')
  const n = s.close.length
  const chg = s.close[n - 1] - s.close[n - 2]
  await expect(page.getByTestId('ohlc-date')).toHaveText('2026/10/30')
  await expect(page.getByTestId('ohlc-open')).toHaveText(f2(s.open[n - 1]))
  await expect(page.getByTestId('ohlc-high')).toHaveText(f2(s.high[n - 1]))
  await expect(page.getByTestId('ohlc-low')).toHaveText(f2(s.low[n - 1]))
  await expect(page.getByTestId('ohlc-close')).toHaveText(f2(s.close[n - 1]))
  await expect(page.getByTestId('ohlc-volume')).toHaveText(s.volume[n - 1].toLocaleString('en-US'))
  await expect(page.getByTestId('ohlc-change')).toHaveText(`${chg > 0 ? '+' : ''}${f2(chg)}`)

  // 主圖與 KD 副圖兩張 canvas 都畫出來了
  await expect(page.getByTestId('chart-price').locator('canvas').first()).toBeVisible()
  await expect(page.getByTestId('chart-kd').locator('canvas').first()).toBeVisible()
  expect(errors).toEqual([])
})

test('均線圖例：預設勾 5／10／20／60，數值等於測試端自己算的簡單平均，可再勾 120／240', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('chart-ma')).toBeVisible()

  for (const m of [5, 10, 20, 60]) await expect(page.getByTestId(`ma-toggle-${m}`)).toBeChecked()
  for (const m of [120, 240]) await expect(page.getByTestId(`ma-toggle-${m}`)).not.toBeChecked()

  const s = chartSeries('0050')
  const last = s.close.length - 1
  for (const m of [5, 10, 20, 60, 120, 240]) await expectNear(page.getByTestId(`ma-val-${m}`), avg(s.close, last, m))

  await page.getByTestId('ma-toggle-120').check()
  await expect(page.getByTestId('ma-toggle-120')).toBeChecked()
  await page.getByTestId('ma-toggle-5').uncheck()
  await expect(page.getByTestId('ma-toggle-5')).not.toBeChecked()
  await expect(page.getByTestId('ma-val-5')).not.toHaveText('—') // 沒勾也還是看得到數值（同 Yahoo）
})

test('KD 圖例：K9／D9／RSV 與測試端自算一致，J9＝3D−2K、K3D2＝3K−2D（Yahoo 口徑）', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('chart-kd-legend')).toBeVisible()

  const s = chartSeries('0050')
  const want = refKd(s)[s.close.length - 1]
  await expectNear(page.getByTestId('kd-k'), want.k)
  await expectNear(page.getByTestId('kd-d'), want.d)
  await expectNear(page.getByTestId('kd-rsv'), want.rsv)
  await expectNear(page.getByTestId('kd-j9'), want.j9)
  await expectNear(page.getByTestId('kd-k3d2'), want.k3d2)

  // 畫面上自己的數字也要互相對得起來
  const k = await numOf(page.getByTestId('kd-k'))
  const d = await numOf(page.getByTestId('kd-d'))
  expect(Math.abs((await numOf(page.getByTestId('kd-j9'))) - (3 * d - 2 * k))).toBeLessThan(0.03)
  expect(Math.abs((await numOf(page.getByTestId('kd-k3d2'))) - (3 * k - 2 * d))).toBeLessThan(0.03)
})

test('十字線：滑過主圖時頂部資訊列、均線與 KD 圖例一起換成那一天；移到 KD 圖也同步；離開回到最新一日', async ({ page }) => {
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  await chartPanel(page).scrollIntoViewIfNeeded()

  const s = chartSeries('0050')
  const kd = refKd(s)
  const check = async () => {
    const label = await page.getByTestId('ohlc-date').innerText()
    const i = DATES.indexOf(label.replace(/\//g, '-'))
    expect(i).toBeGreaterThanOrEqual(8)
    await expect(page.getByTestId('ohlc-close')).toHaveText(f2(s.close[i]))
    await expectNear(page.getByTestId('ma-val-5'), avg(s.close, i, 5))
    await expectNear(page.getByTestId('kd-k'), kd[i].k)
    return label
  }

  const box = await page.getByTestId('chart-price').boundingBox()
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5)
  await expect(page.getByTestId('ohlc-date')).not.toHaveText('2026/10/30')
  const onPrice = await check()
  await page.waitForTimeout(300) // 十字線不會自己彈回最新一日（兩張圖互相觸發會這樣）
  expect(await page.getByTestId('ohlc-date').innerText()).toBe(onPrice)

  const kdBox = await page.getByTestId('chart-kd').boundingBox()
  await page.mouse.move(kdBox.x + kdBox.width * 0.25, kdBox.y + kdBox.height * 0.5)
  await expect(page.getByTestId('ohlc-date')).not.toHaveText(onPrice)
  await check()

  await page.mouse.move(2, 2)
  await expect(page.getByTestId('ohlc-date')).toHaveText('2026/10/30')
})

test('圖上標註清單與急跌表同一組數字；區間最低與其後最低相同、尚未反彈時對應項目不出現', async ({ page }) => {
  const override = {
    '0056': mk('0056', '元大高股息', 'dividend', {
      total: 92.2, drift: 0.0012, last_close: 50,
      event: { window_low: 91.8, window_low_date: '2026-07-29', rebound_high: null, rebound_date: null, rebound_pct: null },
    }),
  }
  await mockApi(page, [], override)
  await page.goto('/etf-compare?symbols=0050,0056')
  const row = sym => page.locator(`[data-testid="event-table"] tr[data-symbol="${sym}"]`)
  const marks = page.getByTestId('chart-marks')
  await expect(marks).toBeVisible()

  // 0050：高 112.30（6/23）、其後最低 91.80（7/29）、區間最低 88.40（6/24，比其後最低更低所以另標）、反彈高點 116.60（10/06）、目前價位 100.00（10/30）
  await expect(page.getByTestId('mark-high')).toContainText('112.30')
  await expect(page.getByTestId('mark-high')).toContainText('06/23')
  await expect(page.getByTestId('mark-low')).toContainText('91.80')
  await expect(page.getByTestId('mark-low')).toContainText('07/29')
  await expect(page.getByTestId('mark-window-low')).toContainText('88.40')
  await expect(page.getByTestId('mark-window-low')).toContainText('06/24')
  await expect(page.getByTestId('mark-rebound')).toContainText('116.60')
  await expect(page.getByTestId('mark-rebound')).toContainText('10/06')
  await expect(page.getByTestId('mark-last')).toContainText('100.00')
  await expect(page.getByTestId('mark-last')).toContainText('10/30')
  // 回落與表格「回落」欄是同一個字串
  const drop = (await row('0050').locator('td').nth(4).innerText()).trim()
  await expect(page.getByTestId('mark-low')).toContainText(`回落 ${drop}`)
  await expect(page.getByTestId('mark-rebound')).toContainText('+27.0%')

  await page.getByTestId('chart-chip-0056').click()
  await expect(page.locator('[data-testid="event-chart"][data-symbol="0056"]')).toBeVisible()
  await expect(page.getByTestId('mark-high')).toContainText('112.30')
  await expect(page.getByTestId('mark-low')).toContainText('91.80')
  await expect(page.getByTestId('mark-window-low')).toHaveCount(0) // 區間最低＝其後最低，不重複標
  await expect(page.getByTestId('mark-rebound')).toHaveCount(0) // 尚未反彈
  await expect(page.getByTestId('mark-last')).toContainText('50.00')
})

test('切換標的：晶片與表格每列的「走勢圖」按鈕都能切；切回已看過的不重抓', async ({ page }) => {
  const chartCalls = []
  await mockApi(page, [], {}, chartCalls)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  const syms = () => chartCalls.map(u => u.searchParams.get('symbol'))
  expect(syms()).toEqual(['0050'])

  const s56 = chartSeries('0056')
  await page.getByTestId('chart-chip-0056').click()
  await expect(page.getByTestId('chart-chip-0056')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('ohlc-close')).toHaveText(f2(s56.close[s56.close.length - 1]))
  expect(syms()).toEqual(['0050', '0056'])

  await page.getByTestId('chart-chip-0050').click()
  await expect(page.getByTestId('ohlc-close')).toHaveText(f2(chartSeries('0050').close[DATES.length - 1]))
  expect(syms()).toEqual(['0050', '0056']) // 已經載過，不再打 API

  // 表格列的按鈕：選到那一檔，並把走勢圖捲到畫面裡
  await page.locator('[data-testid="event-table"] tr[data-symbol="0056"]').getByTestId('show-chart').click()
  await expect(page.getByTestId('chart-chip-0056')).toHaveAttribute('aria-pressed', 'true')
  await expect(chartPanel(page)).toBeInViewport()
})

test('走勢圖載入失敗：只在圖的位置顯示原因與重試，其他表格不受影響；重試成功後出圖', async ({ page }) => {
  await mockApi(page)
  let attempt = 0
  await page.route('**/api/v1/etf-compare/chart**', route => {
    attempt += 1
    if (attempt === 1) {
      route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: '查無日線資料（代碼錯誤或尚未上市）。' }) })
    } else {
      route.fulfill({ status: 200, contentType: 'application/json', body: chartBody('0050') })
    }
  })
  await page.goto('/etf-compare?symbols=0050,0056')

  await expect(page.getByTestId('chart-error')).toContainText('查無日線資料')
  await expect(page.getByTestId('chart-ohlc')).toHaveCount(0)
  await expect(page.locator('[data-testid="event-table"] tr[data-symbol="0050"]')).toBeVisible()

  await page.getByTestId('chart-error').getByRole('button', { name: '重試' }).click()
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  await expect(page.getByTestId('chart-error')).toHaveCount(0)
  expect(attempt).toBe(2)
})

test('改急跌區間只重畫標註，不會重新抓走勢圖資料', async ({ page }) => {
  const chartCalls = []
  await mockApi(page, [], {}, chartCalls)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  expect(chartCalls).toHaveLength(1)

  await page.locator('.event-form input[type="date"]').first().fill('2026-03-02')
  await page.locator('.event-form input[type="date"]').nth(1).fill('2026-04-10')
  await page.getByTestId('apply-range').click()
  await expect(page.getByTestId('event-desc')).toContainText('自訂區間')
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  await expect(page.getByTestId('chart-price').locator('canvas').first()).toBeVisible()
  expect(chartCalls).toHaveLength(1)
})

test('手機：走勢圖不撐寬頁面，圖例會換行，兩張圖都在畫面寬度內', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page)
  await page.goto('/etf-compare?symbols=0050,0056')
  await expect(page.getByTestId('chart-ohlc')).toBeVisible()
  await chartPanel(page).scrollIntoViewIfNeeded()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  for (const id of ['chart-price', 'chart-kd']) {
    const b = await page.getByTestId(id).boundingBox()
    expect(b.x).toBeGreaterThanOrEqual(0)
    expect(b.x + b.width).toBeLessThanOrEqual(390)
  }
  await expect(page.getByTestId('chart-ma')).toBeVisible()
  await expect(page.getByTestId('chart-marks')).toBeVisible()
})
