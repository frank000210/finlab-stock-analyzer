// @ts-check
const { test, expect } = require('@playwright/test')

// 25 closed trades: 2 symbols, 5 months (Jan-May 2026), Mon-Fri dates
// Win pattern: WWWLL repeating — gives 3-win streaks for AAA3 streak detection
// Planned R:R varies by group of 8-9 for AAA2 tier test
// Target always set for AAA2/AAA10 compliance
const makeAAATrades = () => {
  const slots = [
    ['2026-01-05','2026-01-06'], ['2026-01-06','2026-01-07'], ['2026-01-07','2026-01-08'],
    ['2026-01-08','2026-01-09'], ['2026-01-09','2026-01-12'],
    ['2026-02-02','2026-02-03'], ['2026-02-03','2026-02-04'], ['2026-02-04','2026-02-05'],
    ['2026-02-05','2026-02-06'], ['2026-02-06','2026-02-09'],
    ['2026-03-02','2026-03-03'], ['2026-03-03','2026-03-04'], ['2026-03-04','2026-03-05'],
    ['2026-03-05','2026-03-06'], ['2026-03-06','2026-03-09'],
    ['2026-04-01','2026-04-02'], ['2026-04-02','2026-04-03'], ['2026-04-03','2026-04-06'],
    ['2026-04-06','2026-04-07'], ['2026-04-07','2026-04-08'],
    ['2026-05-04','2026-05-05'], ['2026-05-05','2026-05-06'], ['2026-05-06','2026-05-07'],
    ['2026-05-07','2026-05-08'], ['2026-05-08','2026-05-11'],
  ]
  const isWinArr = [true,true,true,false,false, true,true,true,false,false, true,true,true,false,false, true,true,true,false,false, true,true,true,false,false]
  return slots.map(([openDate, exitDate], i) => {
    const symbol = i < 13 ? '2330' : '2454'
    const entry = 600
    const stop = 591 // 1.5% stop → 1 risk unit = 9
    // Vary planned R:R by position: first 8 = low (target ~1R), mid 9 = mid (~2R), last 8 = high (~3R)
    const targetMultiple = i < 8 ? 1 : i < 17 ? 2 : 3
    const target = Math.round(entry + (entry - stop) * targetMultiple)
    const isWin = isWinArr[i]
    const exit = isWin ? Math.round(entry + (entry - stop) * 1.5) : stop - 2
    const lots = [1, 2, 3, 1, 2][i % 5]
    return {
      id: i + 1, symbol, side: 'long', entry, stop, exit, target,
      lots, openDate, exitDate, tag: 'tech', status: 'closed', catalyst: 'breakout',
    }
  })
}

// AAA1: Warren Buffett — top-symbol concentration efficiency
test('AAA1 concentration efficiency shows top symbol avg R vs others', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-concentration-card')).toBeVisible()
  await expect(page.locator('.aaa-concentration-card')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA2: Benjamin Graham — planned R:R quality tiers
test('AAA2 planned R:R quality shows low/mid/high tier avg realized R', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-planned-rr')).toBeVisible()
  await expect(page.locator('.aaa-planned-rr')).toContainText('R:R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA3: Howard Marks — streak-triggered sizing bias
test('AAA3 streak sizing bias shows lots after win vs loss streaks', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-streak-bias')).toBeVisible()
  await expect(page.locator('.aaa-streak-bias')).toContainText('張')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA4: George Soros — reflexivity re-entry tracker
test('AAA4 reflexivity shows first vs subsequent entry avg R per symbol', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-reflexivity')).toBeVisible()
  await expect(page.locator('.aaa-reflexivity')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA5: David Ricardo — win/loss hold duration asymmetry
test('AAA5 duration asymmetry shows avgWinDays vs avgLossDays ratio', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-duration-ratio')).toBeVisible()
  await expect(page.locator('.aaa-duration-ratio')).toContainText('天')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA6: Alexander Elder — impulse trade detector
test('AAA6 impulse trade rate shows % entries within 1 day of a loss', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-impulse-card')).toBeVisible()
  await expect(page.locator('.aaa-impulse-card')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA7: Victor Niederhoffer — trade sequence autocorrelation
test('AAA7 serial autocorrelation shows P(win|prev win) vs P(win|prev loss)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-autocorr')).toBeVisible()
  await expect(page.locator('.aaa-autocorr')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA8: Marty Schwartz — day-of-week performance
test('AAA8 weekday performance shows avg R for Mon-Fri', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-weekday')).toBeVisible()
  expect(await page.locator('.aaa-wd-col').count()).toBe(5)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA9: Monroe Trout — monthly return volatility
test('AAA9 monthly return volatility shows std and monthly breakdown', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-monthly-vol')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.aaa-monthly-vol')).toContainText('R')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// AAA10: Curtis Faith — turtle system compliance rate
test('AAA10 turtle compliance shows stop-set and target-set rates', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeAAATrades())
  await page.reload()

  await expect(page.locator('.aaa-compliance')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.aaa-compliance')).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})
