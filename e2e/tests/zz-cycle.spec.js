// @ts-check
const { test, expect } = require('@playwright/test')

// 30 closed trades: 3 symbols × 3 tags, varied stop distances and hold durations
const makeZZTrades = () => {
  const closed = Array.from({ length: 30 }, (_, i) => {
    const month = String(Math.floor(i / 5) + 1).padStart(2, '0')
    const day = String((i % 5) + 1).padStart(2, '0')
    const holdDays = [1, 3, 7, 14, 2][i % 5]
    const exitDay = String(Number(day) + holdDays).padStart(2, '0')
    const symbol = i < 10 ? '2330' : i < 20 ? '2454' : '2317'
    const tag = i < 10 ? 'tech' : i < 20 ? 'finance' : 'energy'
    const entry = 600
    const stopPcts = [1.5, 3.0, 5.0, 2.5, 1.8]
    const stopPct = stopPcts[i % 5]
    const stop = Math.round(entry * (1 - stopPct / 100))
    const isWin = i % 3 !== 2
    const exit = isWin ? Math.round(entry + (entry - stop) * 1.5) : stop - 2
    return {
      id: i + 1, symbol, side: 'long',
      entry, stop, exit,
      lots: [1, 2, 1, 3, 1][i % 5],
      openDate: `2026-${month}-${day}`,
      exitDate: `2026-${month}-${exitDay}`,
      target: Math.round(entry + (entry - stop) * 2),
      catalyst: ['breakout', 'oversold', 'gap'][i % 3],
      tag, status: 'closed',
    }
  })
  const open = [
    { id: 100, symbol: '2412', side: 'long', entry: 100, stop: 95, lots: 1, openDate: '2026-01-01', tag: 'tech', status: 'open', exit: null, exitDate: null },
  ]
  return [...closed, ...open]
}

// ZZ1: Jesse Livermore — averaging-down detector
test('ZZ1 averaging-down detector shows re-entry rate', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-avgdown-card')).toBeVisible()
  await expect(page.locator('.zz-avgdown-card')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ2: Nassim Taleb — volatility regime performance
test('ZZ2 volatility regime shows avg R per stop-distance tier', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-volreg-card')).toBeVisible()
  await expect(page.locator('.zz-volreg-card')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ3: William Eckhardt — breakeven safety margin
test('ZZ3 breakeven margin shows actual vs required win rate and RR', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-breakeven-card')).toBeVisible()
  await expect(page.locator('.zz-breakeven-card')).toContainText('損益平衡安全邊際')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ4: Stan Druckenmiller — high-conviction avg R check
test('ZZ4 high-conviction sizing shows big vs small lot avg R', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-conviction-card')).toBeVisible()
  await expect(page.locator('.zz-conviction-card')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ5: Larry Williams — hold duration sweet spot
test('ZZ5 hold duration sweet spot shows avg R per duration bucket', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-duration-card')).toBeVisible()
  await expect(page.locator('.zz-dur-bars')).toBeVisible()
  expect(await page.locator('.zz-dur-col').count()).toBe(4)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ6: Peter Lynch — symbol net P&L ranking
test('ZZ6 symbol net P&L shows top contributors', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-symbol-pnl')).toBeVisible()
  await expect(page.locator('.zz-symbol-pnl')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ7: Ed Seykota — tag × month heatmap
test('ZZ7 tag-month heatmap renders table with rows and columns', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-tag-month')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.zz-heatmap-table')).toBeVisible()
  expect(await page.locator('.zz-heatmap-table tbody tr').count()).toBeGreaterThanOrEqual(2)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ8: Richard Dennis — forward loss scenario
test('ZZ8 forward loss scenario shows 3/5/10 consecutive loss drawdowns', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-forward-loss')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.zz-forward-loss')).toContainText('連虧')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ9: Mark Minervini — setup quality tier distribution
test('ZZ9 setup tier distribution shows tight/medium/loose tiers', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-setup-tier')).toBeVisible()
  await expect(page.locator('.zz-setup-tier')).toContainText('進場品質分層')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// ZZ10: Jack Schwager — composite wizard score
test('ZZ10 composite wizard score shows total and 5 component bars', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeZZTrades())
  await page.reload()

  await expect(page.locator('.zz-wizard-score')).toBeVisible({ timeout: 10_000 })
  expect(await page.locator('.zz-wizard-row').count()).toBe(5)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
