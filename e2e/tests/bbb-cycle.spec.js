// @ts-check
const { test, expect } = require('@playwright/test')

// 24 closed + 2 open trades
// Monthly distribution: Jan=2, Feb=4, Mar=10, Apr=8
// Win pattern: W L | W W L W | L L L L L W W W W W | W W L W W W L W
// (Jan:1W1L, Feb:3W1L, Mar:5L then 5W, Apr:6W2L)  → longest streak = 5 losses in Mar
// Lots: cycle [1,2,3,4,1] → Gini variation
// Target: always set for BBB3 exit quality and BBB9/AAA10 compliance
const makeBBBTrades = () => {
  const specs = [
    // Jan (2 trades): low-frequency month for Klarman patience
    { d: '2026-01-05', xd: '2026-01-06', w: true },
    { d: '2026-01-08', xd: '2026-01-09', w: false },
    // Feb (4 trades): mid-frequency
    { d: '2026-02-02', xd: '2026-02-03', w: true },
    { d: '2026-02-05', xd: '2026-02-06', w: true },
    { d: '2026-02-09', xd: '2026-02-10', w: false },
    { d: '2026-02-11', xd: '2026-02-12', w: true },
    // Mar (10 trades): 5 consecutive losses then 5 wins — for BBB8 recovery speed
    { d: '2026-03-02', xd: '2026-03-03', w: false },
    { d: '2026-03-04', xd: '2026-03-05', w: false },
    { d: '2026-03-06', xd: '2026-03-09', w: false },
    { d: '2026-03-10', xd: '2026-03-11', w: false },
    { d: '2026-03-12', xd: '2026-03-13', w: false },
    { d: '2026-03-16', xd: '2026-03-17', w: true },
    { d: '2026-03-18', xd: '2026-03-19', w: true },
    { d: '2026-03-20', xd: '2026-03-23', w: true },
    { d: '2026-03-24', xd: '2026-03-25', w: true },
    { d: '2026-03-26', xd: '2026-03-27', w: true },
    // Apr (8 trades)
    { d: '2026-04-01', xd: '2026-04-02', w: true },
    { d: '2026-04-03', xd: '2026-04-06', w: true },
    { d: '2026-04-07', xd: '2026-04-08', w: false },
    { d: '2026-04-09', xd: '2026-04-10', w: true },
    { d: '2026-04-13', xd: '2026-04-14', w: true },
    { d: '2026-04-15', xd: '2026-04-16', w: true },
    { d: '2026-04-17', xd: '2026-04-22', w: false },
    { d: '2026-04-23', xd: '2026-04-24', w: true },
  ]
  const closed = specs.map(({ d, xd, w }, i) => {
    const entry = 600, stop = 591
    const target = Math.round(entry + (entry - stop) * 2)
    const exit = w ? Math.round(entry + (entry - stop) * 1.5) : stop - 2
    return {
      id: i + 1, symbol: i < 12 ? '2330' : '2454', side: 'long',
      entry, stop, exit, target,
      lots: [1, 2, 3, 4, 1][i % 5],
      openDate: d, exitDate: xd, tag: 'tech', status: 'closed', catalyst: 'breakout',
    }
  })
  const open = [
    { id: 100, symbol: '2412', side: 'long', entry: 100, stop: 95, lots: 2, openDate: '2026-04-25', tag: 'tech', status: 'open', exit: null, exitDate: null, target: 110 },
    { id: 101, symbol: '2317', side: 'long', entry: 200, stop: 192, lots: 1, openDate: '2026-04-26', tag: 'finance', status: 'open', exit: null, exitDate: null, target: 220 },
  ]
  return [...closed, ...open]
}

// BBB1: Ralph Vince — Optimal f position sizing
test('BBB1 optimal f shows Kelly fraction and system edge', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-optimal-f')).toBeVisible()
  await expect(page.locator('.bbb-optimal-f')).toContainText('最優')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB2: Jim Simons — statistical edge decay detection
test('BBB2 edge decay shows recent vs historical avg R', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-edge-decay')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.bbb-edge-decay')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB3: Bernard Baruch — exit quality score
test('BBB3 exit quality shows avg target capture pct for winners', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-exit-quality')).toBeVisible()
  await expect(page.locator('.bbb-exit-quality')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB4: Seth Klarman — patience index
test('BBB4 patience index shows avg monthly R by trade frequency tier', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-patience-index')).toBeVisible()
  await expect(page.locator('.bbb-patience-index')).toContainText('筆')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB5: Dennis Gartman — max single loss control
test('BBB5 max loss control shows maxLoss vs avgWin ratio', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-max-loss-control')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.bbb-max-loss-control')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB6: Gerald Loeb — lot concentration Gini coefficient
test('BBB6 lot Gini shows concentration coefficient and range', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-lot-gini')).toBeVisible()
  await expect(page.locator('.bbb-lot-gini')).toContainText('Gini')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB7: Michael Steinhardt — monthly frequency vs performance correlation
test('BBB7 frequency correlation shows Pearson r of count vs avg R', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-freq-corr')).toBeVisible()
  await expect(page.locator('.bbb-freq-corr')).toContainText('r=')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB8: Joel Greenblatt — losing streak recovery speed
test('BBB8 recovery speed shows longest streak and trades to recover', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-recovery-speed')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.bbb-recovery-speed')).toContainText('連虧')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB9: Larry Hite — open position worst-case loss
test('BBB9 open worst-case shows total stop-out loss for open positions', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-open-worstcase')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.bbb-open-worstcase')).toContainText('開倉')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// BBB10: Philip Fisher — holding duration percentiles
test('BBB10 holding percentiles shows P25/P50/P75 for wins vs losses', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeBBBTrades())
  await page.reload()

  await expect(page.locator('.bbb-holding-pct')).toBeVisible()
  await expect(page.locator('.bbb-holding-pct')).toContainText('天')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
