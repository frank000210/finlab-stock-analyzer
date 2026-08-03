// @ts-check
const { test, expect } = require('@playwright/test')

// UU1 + UU10: Sortino Ratio and System Health Score appear once 10+ closed trades exist
test('UU1+UU10 Sortino Ratio and system health score appear with 10 trades', async ({ page }) => {
  const trades = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    symbol: '2330',
    side: 'long',
    entry: 600,
    stop: 580,
    exit: i < 7 ? 640 : 570, // 7 wins, 3 losses
    lots: 1,
    entryDate: `2026-0${Math.floor(i / 3) + 1}-${String((i % 3) + 2).padStart(2, '0')}`,
    exitDate: `2026-0${Math.floor(i / 3) + 1}-${String((i % 3) + 3).padStart(2, '0')}`,
    tag: 'trend',
    catalyst: 'test',
    status: 'closed',
  }))

  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), trades)
  await page.reload()

  // UU1: Sortino Ratio stat card visible
  await expect(page.getByText('Sortino Ratio')).toBeVisible()

  // UU10: System health score visible with /100 suffix
  await expect(page.locator('.health-score')).toBeVisible()
  await expect(page.locator('.health-total')).toContainText('/100')

  // Clean up
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// UU2: Long/Short split performance table
test('UU2 Long/short split performance renders with mixed-side trades', async ({ page }) => {
  const trades = [
    { id: 1, symbol: '2330', side: 'long',  entry: 600, stop: 580, exit: 640, lots: 1, entryDate: '2026-01-02', exitDate: '2026-01-02', tag: 'trend', status: 'closed' },
    { id: 2, symbol: '2454', side: 'short', entry: 800, stop: 830, exit: 740, lots: 1, entryDate: '2026-01-03', exitDate: '2026-01-03', tag: 'trend', status: 'closed' },
  ]

  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), trades)
  await page.reload()

  await expect(page.getByText('多空分開績效')).toBeVisible()
  await expect(page.locator('table').filter({ hasText: '做多' })).toBeVisible()
  await expect(page.locator('table').filter({ hasText: '做空' })).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// UU3: Breakeven win rate + safety margin in Monte Carlo
test('UU3 breakeven win rate and safety margin displayed in Monte Carlo results', async ({ page }) => {
  await page.goto('/monte-carlo')
  await expect(page.getByRole('heading', { name: /風險模擬/ })).toBeVisible()

  const inputs = page.locator('.inputs input')
  await inputs.nth(0).fill('50') // win rate 50%
  await inputs.nth(1).fill('2')  // payoff R=2, breakeven = 33.3%

  await page.getByRole('button', { name: '執行模擬' }).click()

  await expect(page.getByText('損益平衡最低勝率')).toBeVisible({ timeout: 15_000 })
  // Safety margin = 50% - 33.3% = +16.7%
  await expect(page.locator('.rgrid')).toContainText('33.3%')
  await expect(page.locator('.rgrid')).toContainText('+16.7%')
})

// UU4: R skewness section renders with 3+ closed trades
test('UU4 R skewness section visible with sufficient trade data', async ({ page }) => {
  const trades = [
    { id: 1, symbol: '2330', side: 'long', entry: 600, stop: 580, exit: 640, lots: 1, entryDate: '2026-01-02', exitDate: '2026-01-02', tag: 'trend', status: 'closed' },
    { id: 2, symbol: '2317', side: 'long', entry: 100, stop: 90,  exit: 80,  lots: 1, entryDate: '2026-01-03', exitDate: '2026-01-03', tag: 'trend', status: 'closed' },
    { id: 3, symbol: '2454', side: 'long', entry: 800, stop: 770, exit: 860, lots: 1, entryDate: '2026-01-04', exitDate: '2026-01-04', tag: 'trend', status: 'closed' },
  ]

  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), trades)
  await page.reload()

  await expect(page.getByText('R 分布偏態係數')).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// UU5: Today's trading plan card in Decision view
test('UU5 daily trading plan card renders and persists input', async ({ page }) => {
  await page.goto('/decision')
  await expect(page.getByText('今日交易計劃')).toBeVisible()

  // Initially unset
  await expect(page.getByText('✗ 未設計劃')).toBeVisible()

  // Type a plan
  const textarea = page.locator('.plan-textarea')
  await expect(textarea).toBeVisible()
  await textarea.fill('最大虧損 2%，今天只做趨勢突破，不追強')

  // Status badge changes to set
  await expect(page.getByText('✓ 已設計劃')).toBeVisible()

  // Date label present
  await expect(page.locator('.plan-date')).toContainText('計劃日期：')

  // Clean up
  const key = await page.evaluate(() => {
    const today = new Date().toISOString().slice(0, 10)
    const k = 'finlab_daily_plan_' + today
    localStorage.removeItem(k)
    return k
  })
})

// UU7: Day-of-week performance grid appears with trade data
test('UU7 day-of-week performance grid renders', async ({ page }) => {
  const trades = [
    { id: 1, symbol: '2330', side: 'long', entry: 600, stop: 580, exit: 640, lots: 1, entryDate: '2026-01-06', exitDate: '2026-01-06', tag: 'trend', status: 'closed' },
    { id: 2, symbol: '2454', side: 'long', entry: 800, stop: 770, exit: 860, lots: 1, entryDate: '2026-01-07', exitDate: '2026-01-07', tag: 'trend', status: 'closed' },
  ]

  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), trades)
  await page.reload()

  await expect(page.getByText('依星期幾累計 R')).toBeVisible()
  // Day-of-week cells render (週一 through 週五)
  await expect(page.locator('.dow-grid')).toBeVisible()
  await expect(page.locator('.dow-cell').first()).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// UU8: Tag table shows "近5筆期望值" column
test('UU8 tag table has 近5筆期望值 column', async ({ page }) => {
  const trades = [
    { id: 1, symbol: '2330', side: 'long', entry: 600, stop: 580, exit: 640, lots: 1, entryDate: '2026-01-02', exitDate: '2026-01-02', tag: 'breakout', status: 'closed' },
    { id: 2, symbol: '2454', side: 'long', entry: 800, stop: 770, exit: 860, lots: 1, entryDate: '2026-01-03', exitDate: '2026-01-03', tag: 'breakout', status: 'closed' },
  ]

  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), trades)
  await page.reload()

  await expect(page.getByText('依型態統計')).toBeVisible()
  await expect(page.getByText('近5筆期望值')).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// UU9: ATR stop-distance sanity check in Risk Sizing
test('UU9 ATR stop-distance sanity check appears in checklist', async ({ page }) => {
  await page.goto('/risk-sizing')
  // Wait for market data (ATR) to load
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.mval').first()).not.toHaveText('—')

  // ATR stop-distance message appears in the checklist
  await expect(page.locator('.checklist')).toContainText('ATR', { timeout: 10_000 })
})
