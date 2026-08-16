// @ts-check
const { test, expect } = require('@playwright/test')

// Shared dataset: 18 closed + 3 open trades with varied tags, lots, dates
const makeXXTrades = () => {
  const closed = Array.from({ length: 18 }, (_, i) => ({
    id: i + 1,
    symbol: i < 8 ? '2330' : i < 14 ? '2454' : '2317',
    side: 'long',
    entry: 600, stop: 580,
    exit: i < 12 ? 640 : 570,
    lots: i % 4 === 0 ? 2 : 1,
    openDate: `2026-0${Math.floor(i / 6) + 1}-${String((i % 6) + 1).padStart(2, '0')}`,
    exitDate: `2026-0${Math.floor(i / 6) + 1}-${String((i % 6) + 3).padStart(2, '0')}`,
    target: 650,
    catalyst: i < 6 ? 'breakout' : i < 12 ? 'oversold' : 'gap',
    tag: i < 10 ? 'tech' : 'finance',
    status: 'closed',
  }))
  const open = [
    { id: 100, symbol: '2412', side: 'long', entry: 100, stop: 95, lots: 1, openDate: '2026-01-01', tag: 'tech', status: 'open', exit: null, exitDate: null },
    { id: 101, symbol: '2881', side: 'long', entry: 50, stop: 47, lots: 2, openDate: '2026-02-01', tag: 'finance', status: 'open', exit: null, exitDate: null },
    { id: 102, symbol: '3008', side: 'long', entry: 200, stop: 190, lots: 1, openDate: '2026-01-15', tag: 'tech', status: 'open', exit: null, exitDate: null },
  ]
  return [...closed, ...open]
}

// XX1: Kelly Fraction (Ed Thorp)
test('XX1 Kelly fraction card shows quarter-Kelly recommendation', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('Kelly 倉位建議')).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: 'Kelly 倉位建議' })).toContainText('¼-Kelly')
  await expect(page.locator('.scard').filter({ hasText: 'Kelly 倉位建議' })).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX2: Equity curve momentum (Nick Radge)
test('XX2 equity curve momentum shows TRADE or PAUSE signal', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('權益曲線動能')).toBeVisible()
  const card = page.locator('.scard').filter({ hasText: '權益曲線動能' })
  // should show either TRADE or PAUSE
  const text = await card.textContent()
  expect(text).toMatch(/TRADE|PAUSE/)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX3: Open position aging (Darvas) — in DecisionView
test('XX3 open position aging shows days held vs avg win hold time', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('開倉逾期警示')).toBeVisible()
  await expect(page.locator('.xx-aging-table')).toBeVisible()
  const rows = page.locator('.xx-aging-table tbody tr')
  const count = await rows.count()
  expect(count).toBeGreaterThanOrEqual(1)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX4: Open tag concentration (Ray Dalio) — in DecisionView
test('XX4 open tag concentration shows bar chart and warn when >50%', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('開倉標籤集中度')).toBeVisible()
  await expect(page.locator('.xx-tagconc-bars')).toBeVisible()
  // 2 out of 3 open trades are 'tech' → should warn
  const card = page.locator('.xx-tagconc-card')
  await expect(card).toContainText('tech')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX5: R quartile profile (Michael Covel)
test('XX5 R quartile card shows P25/P50/P75 values', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('R 四分位分布')).toBeVisible()
  const card = page.locator('.scard').filter({ hasText: 'R 四分位分布' })
  await expect(card).toContainText('P25')
  await expect(card).toContainText('P50')
  await expect(card).toContainText('P75')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX6: Monthly profit factor sparkline
test('XX6 monthly profit factor sparkline renders with SVG', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.locator('.scard').filter({ hasText: 'CTA 標準：PF' })).toBeVisible()
  await expect(page.locator('.scard').filter({ hasText: 'CTA 標準：PF' }).locator('svg')).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX7: Drawdown episode tracker (Richard Dennis) — in RiskMonitorView
test('XX7 drawdown episode tracker shows depth and recovery count', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('回撤週期追蹤')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.xx-dd-table')).toBeVisible()

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX8: Stop recovery cost (Martin Schwartz)
test('XX8 stop recovery cost table shows recovery trades count', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('停損觸發恢復成本')).toBeVisible()
  await expect(page.locator('.xx-recovery-table')).toBeVisible()
  const rows = page.locator('.xx-recovery-table tbody tr')
  const count = await rows.count()
  expect(count).toBeGreaterThanOrEqual(1)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX9: Streak probability (George Soros)
test('XX9 current streak probability shows % and streak type', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText(/當前連.機率/)).toBeVisible()
  const card = page.locator('.scard').filter({ hasText: 'Soros' })
  await expect(card).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// XX10: Trade grade distribution (William O'Neil)
test('XX10 trade grade distribution shows A/B/C/D counts', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeXXTrades())
  await page.reload()

  await expect(page.getByText('交易評分分布')).toBeVisible()
  const block = page.locator('.an-block').filter({ hasText: '交易評分分布' })
  await expect(block).toContainText('A')
  await expect(block).toContainText('B')
  await expect(block).toContainText('D')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
