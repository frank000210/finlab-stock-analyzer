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
async function mockApi(page, calls = [], override = {}) {
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

  const heads = await page.locator('[data-testid="event-table"] thead th').allInnerTexts()
  expect(heads.slice(0, 6)).toEqual(['標的', '區間最低', '區間最高', '其後最低', '回落', '目前價位'])

  // 區間最低 88.40（6/24，在高點之前）；其後最低 91.80（7/29）；目前價位 = 最新收盤 100.00（10/30）
  await expect(row('0050').getByTestId('window-low')).toContainText('88.40')
  await expect(row('0050').getByTestId('window-low')).toContainText('06/24')
  await expect(row('0050')).toContainText('91.80')
  await expect(row('0050').getByTestId('last-price')).toContainText('100.00')
  await expect(row('0050').getByTestId('last-price')).toContainText('10/30')
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
