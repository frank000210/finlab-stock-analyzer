// @ts-check
const { test, expect } = require('@playwright/test')

// Shared dataset: 12 closed trades with catalyst, symbol variety + 2 open
const makeVVTrades = () => {
  const closed = Array.from({ length: 12 }, (_, i) => ({
    id: i + 1,
    symbol: i < 6 ? '2330' : i < 9 ? '2454' : '2317',
    side: 'long',
    entry: 600, stop: 580,
    exit: i < 8 ? 640 : 570,
    lots: 1,
    openDate: `2026-0${Math.floor(i / 4) + 1}-${String((i % 4) + 1).padStart(2, '0')}`,
    exitDate: `2026-0${Math.floor(i / 4) + 1}-${String((i % 4) + 2).padStart(2, '0')}`,
    tag: i < 6 ? 'trend' : 'reversal',
    catalyst: i < 4 ? 'breakout' : i < 8 ? 'oversold' : 'gap',
    status: 'closed',
  }))
  const open = [
    { id: 100, symbol: '2330', side: 'long', entry: 600, stop: 580, lots: 2, status: 'open', openDate: '2026-08-01', catalyst: 'breakout' },
    { id: 101, symbol: '2454', side: 'long', entry: 800, stop: 770, lots: 1, status: 'open', openDate: '2026-08-02', catalyst: 'oversold' },
  ]
  return [...closed, ...open]
}

// VV1: Current streak card (Mark Douglas)
test('VV1 current active streak card shows win/loss count', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  // Last 4 closed trades are losses (gap) → shows 連敗
  await expect(page.getByText(/當前連[勝敗]/)).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: '當前連' })).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV2: Recovery Factor (CTA standard)
test('VV2 Recovery Factor stat card renders with correct value', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  await expect(page.getByText('Recovery Factor')).toBeVisible()
  // totalR=10, maxDD=6 → RF=1.67
  await expect(page.locator('.scard').filter({ hasText: 'Recovery Factor' })).toContainText('1.67')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV3: Catalyst analytics table (O'Neil CAN SLIM)
test('VV3 catalyst analytics table renders with catalyst groups', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  await expect(page.getByText('依進場理由統計')).toBeVisible()
  await expect(page.locator('table').filter({ hasText: 'breakout' })).toBeVisible()
  await expect(page.locator('table').filter({ hasText: 'oversold' })).toBeVisible()
  await expect(page.locator('table').filter({ hasText: 'gap' })).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV4: Trade frequency warning (Van Tharp)
test('VV4 trade frequency card shows trades per week', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  await expect(page.getByText('交易頻率')).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: '交易頻率' })).toContainText('筆/週')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV5: Consecutive losses to ruin in Monte Carlo (Taleb ergodicity)
test('VV5 consecutive losses to ruin card appears in Monte Carlo results', async ({ page }) => {
  await page.goto('/monte-carlo')
  await expect(page.getByRole('heading', { name: /風險模擬/ })).toBeVisible()

  const inputs = page.locator('.inputs input')
  await inputs.nth(0).fill('55')  // win rate
  await inputs.nth(1).fill('2')   // payoff R=2
  await inputs.nth(2).fill('2')   // risk 2%

  await page.getByRole('button', { name: '執行模擬' }).click()

  await expect(page.getByText('最少連虧幾筆觸及破產')).toBeVisible({ timeout: 15_000 })
  // With 2% risk and default 50% ruin threshold: ceil(log(0.5)/log(0.98)) ≈ 34
  await expect(page.locator('.rgrid')).toContainText('筆')
})

// VV6: Minimum viable R:R in RiskSizing (PTJ defense)
test('VV6 minimum R:R checklist item appears after loading journal win rate', async ({ page }) => {
  // Pre-load journal data so 從日誌帶入 has data
  const trades = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1, symbol: '2330', side: 'long', entry: 600, stop: 580,
    exit: i < 7 ? 640 : 570, lots: 1,
    exitDate: `2026-0${Math.floor(i / 5) + 1}-${String((i % 5) + 2).padStart(2, '0')}`,
    tag: 'trend', catalyst: 'breakout', status: 'closed',
  }))
  await page.goto('/risk-sizing')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), trades)

  // Wait for market data then click 從日誌帶入
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })
  const journalBtn = page.getByRole('button', { name: /日誌帶入/ })
  await journalBtn.click()

  // VV6 checklist item should now appear
  await expect(page.locator('.checklist')).toContainText('最低需要', { timeout: 10_000 })
  await expect(page.locator('.checklist')).toContainText('R:R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV7: Symbol concentration warning (Templeton diversification)
test('VV7 symbol concentration bars render and warn when top symbol > 30%', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  await expect(page.getByText('標的集中度')).toBeVisible()
  // 2330 has 6/12 trades = ~55% of absolute R → concentration warning
  await expect(page.locator('.conc-row')).toBeVisible()
  await expect(page.locator('.conc-row')).toContainText('2330')
  // Warning text appears because 2330 > 30%
  await expect(page.getByText(/集中度偏高/)).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV8: Open position total heat % (Van Tharp Total Heat)
test('VV8 open position total heat % appears when account size is set', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify(t))
    localStorage.setItem('finlab_sizing_account', '1000000')
  }, makeVVTrades())
  await page.reload()

  await expect(page.getByText('總風險熱度')).toBeVisible()
  // 2330: 2lots×1000×|600-580|=40,000 + 2454: 1lot×1000×|800-770|=30,000 = 70,000/1M = 7.0%
  await expect(page.locator('.scard').filter({ hasText: '總風險熱度' })).toContainText('7.0%')

  await page.evaluate(() => {
    localStorage.removeItem('finlab_trade_journal')
    localStorage.removeItem('finlab_sizing_account')
  })
})

// VV9: Distance from equity high-water mark (RiskMonitor)
test('VV9 equity high-water mark distance shows in risk monitor', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  await expect(page.getByText('R 曲線高水位')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.r-curve-stats').filter({ hasText: 'R 曲線高水位' })).toContainText('R')
  // Current equity=10, HWM=16, drawdown=6
  await expect(page.locator('.r-curve-stats').filter({ hasText: 'R 曲線高水位' })).toContainText('16.0R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// VV10: Outlier fragility analysis (Taleb)
test('VV10 outlier trade fragility analysis renders in journal', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeVVTrades())
  await page.reload()

  await expect(page.getByText('異常大贏依賴度')).toBeVisible()
  // With 8 wins at +2R each, top3=6R, totalPos=16R → 37.5% < 50% → healthy
  await expect(page.locator('.an-block').filter({ hasText: '異常大贏依賴度' })).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
