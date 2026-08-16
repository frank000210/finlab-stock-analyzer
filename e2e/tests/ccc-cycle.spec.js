// @ts-check
const { test, expect } = require('@playwright/test')

// 25 closed trades covering CCC1-CCC10 scenarios
// Symbols: 2330(12), 2454(8), 2412(3), 2317(2) → HHI ~0.35, high concentration
// Catalysts: breakout / earnings / trend (3 groups, each ≥2 trades)
// Win pattern: first-10 = 4W6L (40%), last-10 = 8W2L (80%) → improving trend
// All trades have target set (tgtMult 2 or 3) for CCC1 planned R/R
// Risk varies (5-9 pts) for CCC6 VCP correlation
const makeCCCTrades = () => {
  const specs = [
    // Jan: 5 trades — first 10 start here
    { d:'2026-01-05',xd:'2026-01-06',w:true,  sym:'2330',cat:'breakout',entry:600,stop:594,tgtMult:2 },
    { d:'2026-01-08',xd:'2026-01-09',w:false, sym:'2454',cat:'earnings', entry:300,stop:291,tgtMult:2 },
    { d:'2026-01-12',xd:'2026-01-13',w:false, sym:'2330',cat:'trend',    entry:600,stop:591,tgtMult:2 },
    { d:'2026-01-15',xd:'2026-01-16',w:true,  sym:'2412',cat:'breakout', entry:100,stop:95, tgtMult:2 },
    { d:'2026-01-19',xd:'2026-01-20',w:false, sym:'2454',cat:'earnings', entry:300,stop:292,tgtMult:2 },
    // Feb: 5 trades
    { d:'2026-02-02',xd:'2026-02-03',w:true,  sym:'2330',cat:'trend',    entry:600,stop:594,tgtMult:2 },
    { d:'2026-02-05',xd:'2026-02-06',w:false, sym:'2454',cat:'breakout', entry:300,stop:291,tgtMult:3 },
    { d:'2026-02-09',xd:'2026-02-10',w:true,  sym:'2330',cat:'earnings', entry:600,stop:595,tgtMult:2 },
    { d:'2026-02-12',xd:'2026-02-13',w:false, sym:'2317',cat:'trend',    entry:200,stop:194,tgtMult:2 },
    { d:'2026-02-16',xd:'2026-02-17',w:false, sym:'2330',cat:'breakout', entry:600,stop:591,tgtMult:2 },
    // Mar: 5 trades — second half begins
    { d:'2026-03-02',xd:'2026-03-05',w:true,  sym:'2454',cat:'earnings', entry:300,stop:292,tgtMult:2 },
    { d:'2026-03-06',xd:'2026-03-09',w:true,  sym:'2330',cat:'trend',    entry:600,stop:594,tgtMult:3 },
    { d:'2026-03-10',xd:'2026-03-13',w:false, sym:'2330',cat:'breakout', entry:600,stop:591,tgtMult:2 },
    { d:'2026-03-16',xd:'2026-03-17',w:true,  sym:'2454',cat:'trend',    entry:300,stop:293,tgtMult:3 },
    { d:'2026-03-18',xd:'2026-03-19',w:true,  sym:'2412',cat:'earnings', entry:100,stop:95, tgtMult:2 },
    // Apr: 5 trades — last 10 start at index 15
    { d:'2026-04-01',xd:'2026-04-03',w:true,  sym:'2330',cat:'breakout', entry:600,stop:595,tgtMult:3 },
    { d:'2026-04-06',xd:'2026-04-08',w:true,  sym:'2454',cat:'earnings', entry:300,stop:293,tgtMult:2 },
    { d:'2026-04-09',xd:'2026-04-10',w:false, sym:'2330',cat:'trend',    entry:600,stop:591,tgtMult:2 },
    { d:'2026-04-13',xd:'2026-04-14',w:true,  sym:'2454',cat:'breakout', entry:300,stop:294,tgtMult:3 },
    { d:'2026-04-15',xd:'2026-04-16',w:true,  sym:'2317',cat:'earnings', entry:200,stop:194,tgtMult:2 },
    // May: 5 trades
    { d:'2026-05-04',xd:'2026-05-07',w:true,  sym:'2330',cat:'breakout', entry:600,stop:595,tgtMult:3 },
    { d:'2026-05-08',xd:'2026-05-09',w:true,  sym:'2454',cat:'trend',    entry:300,stop:293,tgtMult:2 },
    { d:'2026-05-12',xd:'2026-05-13',w:false, sym:'2330',cat:'earnings', entry:600,stop:594,tgtMult:3 },
    { d:'2026-05-14',xd:'2026-05-15',w:true,  sym:'2412',cat:'breakout', entry:100,stop:95, tgtMult:2 },
    { d:'2026-05-19',xd:'2026-05-20',w:true,  sym:'2330',cat:'trend',    entry:600,stop:594,tgtMult:3 },
  ]
  return specs.map(({ d, xd, w, sym, cat, entry, stop, tgtMult }, i) => {
    const risk = Math.abs(entry - stop)
    const target = Math.round(entry + risk * tgtMult)
    const exit = w ? Math.round(entry + risk * 1.5) : stop - 1
    return {
      id: i + 1, symbol: sym, side: 'long',
      entry, stop, exit, target,
      lots: [1, 2, 3, 1, 2][i % 5],
      openDate: d, exitDate: xd, tag: 'tech', status: 'closed',
      catalyst: cat,
    }
  })
}

// CCC1: Jesse Livermore — Planned R/R Distribution
test('CCC1 planned RR distribution shows quality bucket percentages', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-rrplan')).toBeVisible()
  await expect(page.locator('.ccc-rrplan')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC2: Nicolas Darvas — Symbol Selectivity Index
test('CCC2 symbol selectivity shows unique count and avg trades per symbol', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-selectivity')).toBeVisible()
  await expect(page.locator('.ccc-selectivity')).toContainText('筆')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC3: William O'Neil — Catalyst Win Rate
test('CCC3 catalyst win rate groups trades by catalyst tag', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-catalyst')).toBeVisible()
  await expect(page.locator('.ccc-catalyst')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC4: Stan Weinstein — Rolling Win Rate Trajectory
test('CCC4 rolling win rate trend shows first-10 vs last-10 improvement', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-rollwinrate')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ccc-rollwinrate')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC5: Ed Seykota — Streak Frequency Histogram
test('CCC5 streak frequency shows consecutive loss distribution', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-streakfreq')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ccc-streakfreq')).toContainText('連虧')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC6: Mark Minervini — VCP Tightness vs R Correlation
test('CCC6 VCP correlation shows Pearson r of stop tightness vs realized R', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-vcp')).toBeVisible()
  await expect(page.locator('.ccc-vcp')).toContainText('r=')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC7: Paul Tudor Jones — R Multiple Distribution Bins
test('CCC7 R bin distribution shows breakdown across 5 buckets', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-rbins')).toBeVisible()
  await expect(page.locator('.ccc-rbins')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC8: Van Tharp — System Quality Number
test('CCC8 SQN shows system quality rating and mean/std R', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-sqn')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ccc-sqn')).toContainText('SQN')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC9: Bruce Kovner — Symbol HHI Diversification
test('CCC9 symbol HHI shows concentration index and diversity rating', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-symbol-hhi')).toBeVisible()
  await expect(page.locator('.ccc-symbol-hhi')).toContainText('HHI')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// CCC10: Richard Donchian — Win Holding Duration Trend
test('CCC10 win duration trend shows early vs recent median holding days', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeCCCTrades())
  await page.reload()

  await expect(page.locator('.ccc-duration-trend')).toBeVisible()
  await expect(page.locator('.ccc-duration-trend')).toContainText('天')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
