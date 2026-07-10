// @ts-check
const { test, expect } = require('@playwright/test')

const SIGNALS = {
  success: true,
  data: {
    as_of: '2026-07-08',
    items: [
      { symbol: '2882', ok: true, price: 65, chg_pct: 1.0, trend: '多頭排列', rsi: 55, stop_dist_pct: 5, vol_ratio: 1.2, range_pos_pct: 60, setup_total: 72, setup_verdict: '進場條件佳', tags: [{ t: '多頭排列', tone: 'up' }] },
      { symbol: '2330', ok: true, price: 2440, chg_pct: -0.8, trend: '多頭排列', rsi: 56, stop_dist_pct: 5, vol_ratio: 0.6, range_pos_pct: 90, setup_total: 55, setup_verdict: '普通，需再確認', tags: [{ t: '多頭排列', tone: 'up' }] },
    ],
  },
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/risk/watchlist-signals*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SIGNALS) })
  })
  // 預設體制 mock：進攻 ×1.0（個別測試可用後註冊的 route 覆蓋）
  await page.route('**/api/v1/risk/market-regime', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { regime: 'offense', label: '進攻', risk_mult: 1.0, proxy: '0050', close: 60, ma200: 55, above_ma200: true, ma200_rising: true, mom20_pct: 2.5, as_of: '2026-07-10' } }),
    })
  })
})

async function seed(page) {
  await page.goto('/command')
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882', '2330']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
    localStorage.removeItem('finlab_trade_journal')
  })
  await page.reload()
}

test('作戰台 ranks watchlist and computes suggested lots', async ({ page }) => {
  await seed(page)
  await expect(page.locator('.cmd-table tbody tr')).toHaveCount(2)

  // budget = 1,000,000 * 1% = 10,000; 2882 risk/share = 65*5% = 3.25 -> ~3076 shares -> 3 lots.
  const row2882 = page.locator('.cmd-table tbody tr', { hasText: '2882' })
  await expect(row2882).toContainText('3 張')
  await expect(page.locator('.cmd-table .score').first()).toContainText('72') // best-first
})

test('作戰台 記錄 writes an open trade to the journal', async ({ page }) => {
  await seed(page)
  const row2882 = page.locator('.cmd-table tbody tr', { hasText: '2882' })
  await row2882.getByRole('button', { name: '記錄' }).click()

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal.length).toBe(1)
  expect(journal[0].symbol).toBe('2882')
  expect(journal[0].lots).toBe(3)
  expect(journal[0].status).toBe('open')
})

test('作戰台 suggests risk% from journal half-Kelly', async ({ page }) => {
  await page.goto('/command')
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882', '2330']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
    // 2 wins (+20k,+10k), 1 loss (-15k) -> W=2/3, PF=2 -> half-Kelly capped at 10%.
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 120, lots: 1 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 85, lots: 1 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 110, lots: 1 },
    ]))
  })
  await page.reload()

  await expect(page.locator('.kelly-hint')).toContainText('10.0%')
  await page.locator('.kelly-hint .link-btn').click()
  await expect(page.locator('.inp.w70')).toHaveValue('10')
})

test('作戰台 market regime scales suggested lots (B5)', async ({ page }) => {
  await page.route('**/api/v1/risk/market-regime', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { regime: 'defense', label: '防守', risk_mult: 0.5, proxy: '0050', close: 50, ma200: 55, above_ma200: false, ma200_rising: false, mom20_pct: -3.1, as_of: '2026-07-10' } }),
    })
  })
  await seed(page)

  await expect(page.locator('.regime-strip')).toContainText('防守')
  await expect(page.locator('.regime-strip')).toContainText('×0.5')
  // 1% base × 0.5 = 0.5% -> budget 5,000; 2882 risk/share 3.25 -> 1538 shares -> 1 lot（未套用時為 3 張）
  await expect(page.locator('.regime-strip')).toContainText('有效單筆風險 0.50%')
  const row2882 = page.locator('.cmd-table tbody tr', { hasText: '2882' })
  await expect(row2882).toContainText('1 張')

  // 取消套用 → 回到 3 張
  await page.locator('.rg-apply input').uncheck()
  await expect(row2882).toContainText('3 張')
})

test('作戰台 warns when top picks are highly correlated', async ({ page }) => {
  await page.route('**/api/v1/risk/correlation*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbols: ['2882', '2330'], matrix: [[1, 0.88], [0.88, 1]], pairs: [{ a: '2882', b: '2330', corr: 0.88 }], high_pairs: [{ a: '2882', b: '2330', corr: 0.88 }], high_threshold: 0.7, avg_abs_corr: 0.88, days: 60 } }),
    })
  })
  await seed(page)

  await expect(page.locator('.corr-warn')).toContainText('0.88')
  await expect(page.locator('.corr-warn')).toContainText('同一注')
})
