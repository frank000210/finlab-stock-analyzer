// @ts-check
const { test, expect } = require('@playwright/test')

// 25 closed trades for DDD cycle
// Lynch: mix of 1-day and 3-4 day holds
// Dreman: two loss streaks of 3 (Jan idx 0-2, Mar idx 10-12) → post-streak trades
// Dalio: 5 months each with ≥2 trades, Feb/Apr/May positive, Jan/Mar negative
// Taleb: all losses ≈ -1.1R (uniform), maxToAvgRatio ≈ 1.0, tailFreq = 0% → protected
// Schloss: all losers exit at stop-1 → actual loss = risk+1, ≤1.5× planned risk
// Templeton: tags = tech(15)/biotech(5)/finance(5) → HHI ≈ 0.44 (concentrated)
// Cohen: all exits on unique dates → 16 profit days avg +1.5R, 9 loss days ≈ -1.15R
// Ackman: lots vary 1/2/3/4 with varied W/L pattern
// Swensen: Feb and Apr are good months (4.8R), Mar and May follow them
const makeDDDTrades = () => {
  const specs = [
    // Jan: L,L,L,W(≥3d),W(≥3d) — streak of 3 losses, two patient holds after
    { d:'2026-01-05',xd:'2026-01-06',w:false,sym:'2330',tag:'tech',   cat:'breakout',entry:600,stop:594,lots:1,tgtMult:2 },
    { d:'2026-01-07',xd:'2026-01-08',w:false,sym:'2330',tag:'tech',   cat:'earnings', entry:600,stop:594,lots:2,tgtMult:2 },
    { d:'2026-01-09',xd:'2026-01-10',w:false,sym:'2454',tag:'tech',   cat:'trend',    entry:300,stop:291,lots:3,tgtMult:2 },
    { d:'2026-01-13',xd:'2026-01-15',w:true, sym:'2454',tag:'tech',   cat:'breakout', entry:300,stop:294,lots:4,tgtMult:3 },
    { d:'2026-01-16',xd:'2026-01-20',w:true, sym:'2412',tag:'biotech',cat:'earnings', entry:100,stop:95, lots:1,tgtMult:2 },
    // Feb: W,W,L,W,W(≥3d) — positive month
    { d:'2026-02-02',xd:'2026-02-03',w:true, sym:'2317',tag:'finance',cat:'breakout', entry:200,stop:194,lots:2,tgtMult:2 },
    { d:'2026-02-05',xd:'2026-02-06',w:true, sym:'2330',tag:'tech',   cat:'trend',    entry:600,stop:595,lots:3,tgtMult:3 },
    { d:'2026-02-09',xd:'2026-02-10',w:false,sym:'2454',tag:'tech',   cat:'earnings', entry:300,stop:292,lots:1,tgtMult:2 },
    { d:'2026-02-11',xd:'2026-02-12',w:true, sym:'2412',tag:'biotech',cat:'breakout', entry:100,stop:95, lots:2,tgtMult:2 },
    { d:'2026-02-13',xd:'2026-02-16',w:true, sym:'2317',tag:'finance',cat:'trend',    entry:200,stop:193,lots:4,tgtMult:3 },
    // Mar: L,L,L,W,W — second streak of 3 losses, post-streak wins
    { d:'2026-03-02',xd:'2026-03-03',w:false,sym:'2330',tag:'tech',   cat:'trend',    entry:600,stop:591,lots:1,tgtMult:2 },
    { d:'2026-03-04',xd:'2026-03-05',w:false,sym:'2330',tag:'tech',   cat:'breakout', entry:600,stop:591,lots:2,tgtMult:2 },
    { d:'2026-03-06',xd:'2026-03-09',w:false,sym:'2454',tag:'tech',   cat:'earnings', entry:300,stop:291,lots:3,tgtMult:2 },
    { d:'2026-03-10',xd:'2026-03-11',w:true, sym:'2317',tag:'finance',cat:'breakout', entry:200,stop:194,lots:4,tgtMult:3 },
    { d:'2026-03-12',xd:'2026-03-13',w:true, sym:'2412',tag:'biotech',cat:'trend',    entry:100,stop:95, lots:1,tgtMult:2 },
    // Apr: W,W(≥3d),L,W,W — positive month
    { d:'2026-04-01',xd:'2026-04-02',w:true, sym:'2330',tag:'tech',   cat:'earnings', entry:600,stop:595,lots:2,tgtMult:2 },
    { d:'2026-04-06',xd:'2026-04-09',w:true, sym:'2454',tag:'tech',   cat:'breakout', entry:300,stop:294,lots:3,tgtMult:3 },
    { d:'2026-04-13',xd:'2026-04-14',w:false,sym:'2330',tag:'tech',   cat:'trend',    entry:600,stop:591,lots:4,tgtMult:2 },
    { d:'2026-04-15',xd:'2026-04-16',w:true, sym:'2317',tag:'finance',cat:'earnings', entry:200,stop:194,lots:1,tgtMult:2 },
    { d:'2026-04-17',xd:'2026-04-18',w:true, sym:'2412',tag:'biotech',cat:'breakout', entry:100,stop:95, lots:2,tgtMult:3 },
    // May: W,W,W,W,L — follows good Apr month (tests DDD10 post-good-month)
    { d:'2026-05-04',xd:'2026-05-05',w:true, sym:'2330',tag:'tech',   cat:'trend',    entry:600,stop:595,lots:3,tgtMult:3 },
    { d:'2026-05-07',xd:'2026-05-08',w:true, sym:'2454',tag:'tech',   cat:'earnings', entry:300,stop:294,lots:4,tgtMult:2 },
    { d:'2026-05-11',xd:'2026-05-12',w:true, sym:'2330',tag:'tech',   cat:'breakout', entry:600,stop:595,lots:1,tgtMult:3 },
    { d:'2026-05-13',xd:'2026-05-14',w:true, sym:'2317',tag:'finance',cat:'trend',    entry:200,stop:194,lots:2,tgtMult:2 },
    { d:'2026-05-15',xd:'2026-05-16',w:false,sym:'2412',tag:'biotech',cat:'earnings', entry:100,stop:95, lots:3,tgtMult:2 },
  ]
  return specs.map(({ d, xd, w, sym, tag, cat, entry, stop, lots, tgtMult }, i) => {
    const risk = Math.abs(entry - stop)
    const target = Math.round(entry + risk * tgtMult)
    const exit = w ? Math.round(entry + risk * 1.5) : stop - 1
    return {
      id: i + 1, symbol: sym, side: 'long',
      entry, stop, exit, target, lots,
      openDate: d, exitDate: xd, tag, status: 'closed', catalyst: cat,
    }
  })
}

// DDD1: Peter Lynch — Holding Duration Segmentation
test('DDD1 Lynch holding segmentation shows quick vs patient hold avg R', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-lynch-hold')).toBeVisible()
  await expect(page.locator('.ddd-lynch-hold')).toContainText('天')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD2: David Dreman — Post-Loss-Streak Contrarian Recovery
test('DDD2 Dreman contrarian shows post-streak avg R vs baseline', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-dreman-streak')).toBeVisible()
  await expect(page.locator('.ddd-dreman-streak')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD3: Ray Dalio — Monthly R Sharpe Profile
test('DDD3 Dalio monthly Sharpe shows per-month risk-adjusted return', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-dalio-sharpe')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ddd-dalio-sharpe')).toContainText('Sharpe')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD4: Nassim Taleb — Fat Tail Protection Score
test('DDD4 Taleb fat tail shows tail loss frequency and max/avg ratio', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-taleb-tail')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ddd-taleb-tail')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD5: Charlie Munger — Multi-Condition Alignment Score
test('DDD5 Munger alignment shows avg R by condition score (0-3)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-munger-align')).toBeVisible()
  await expect(page.locator('.ddd-munger-align')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD6: Walter Schloss — Stop Discipline Rate
test('DDD6 Schloss stop discipline shows % of losers within planned risk', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-schloss-stop')).toBeVisible()
  await expect(page.locator('.ddd-schloss-stop')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD7: John Templeton — Tag HHI Diversification
test('DDD7 Templeton tag HHI shows sector/style concentration index', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-templeton-hhi')).toBeVisible()
  await expect(page.locator('.ddd-templeton-hhi')).toContainText('HHI')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD8: Steve Cohen — Max Daily Loss vs Avg Profit Day
test('DDD8 Cohen daily control shows max loss day vs avg profit day ratio', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-cohen-daily')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ddd-cohen-daily')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD9: Bill Ackman — Lot Conviction vs Outcome Correlation
test('DDD9 Ackman conviction shows Pearson r of lots vs realized R', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-ackman-lots')).toBeVisible()
  await expect(page.locator('.ddd-ackman-lots')).toContainText('r=')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// DDD10: David Swensen — Post-Good-Month Performance
test('DDD10 Swensen post-good-month shows performance after top-quartile months', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeDDDTrades())
  await page.reload()

  await expect(page.locator('.ddd-swensen-decay')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.ddd-swensen-decay')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
