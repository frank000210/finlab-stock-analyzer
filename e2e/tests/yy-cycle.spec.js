// @ts-check
const { test, expect } = require('@playwright/test')

// 30 closed trades across 6 months, 3 catalysts, varying lots, with targets
const makeYYTrades = () => {
  const closed = Array.from({ length: 30 }, (_, i) => {
    const month = String(Math.floor(i / 5) + 1).padStart(2, '0')
    const day = String((i % 5) + 1).padStart(2, '0')
    return {
      id: i + 1,
      symbol: i < 10 ? '2330' : i < 20 ? '2454' : '2317',
      side: 'long',
      entry: 600, stop: 580,
      exit: i % 3 !== 2 ? 640 : 570,
      lots: [1, 2, 1, 3, 1][i % 5],
      openDate: `2026-${month}-${day}`,
      exitDate: `2026-${month}-${String(Number(day) + 2).padStart(2, '0')}`,
      target: 650,
      catalyst: ['breakout', 'oversold', 'gap'][i % 3],
      tag: i < 15 ? 'tech' : 'finance',
      status: 'closed',
    }
  })
  const open = [
    { id: 100, symbol: '2412', side: 'long', entry: 100, stop: 95, lots: 1, openDate: '2026-01-01', tag: 'tech', status: 'open', exit: null, exitDate: null },
    { id: 101, symbol: '2881', side: 'long', entry: 50, stop: 47, lots: 2, openDate: '2026-02-01', tag: 'finance', status: 'open', exit: null, exitDate: null },
  ]
  return [...closed, ...open]
}

// YY1: Van Tharp SQN
test('YY1 SQN card shows system quality score and label', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.locator('.scard').filter({ hasText: '系統品質分數' })).toBeVisible()
  const card = page.locator('.scard').filter({ hasText: 'SQN' }).first()
  const text = await card.textContent()
  expect(text).toMatch(/良好|優秀|普通|差/)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY2: Catalyst breakdown
test('YY2 catalyst breakdown table shows per-catalyst stats', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.getByText('催化劑績效分層')).toBeVisible()
  await expect(page.locator('.yy-catalyst-table')).toBeVisible()
  const rows = page.locator('.yy-catalyst-table tbody tr')
  expect(await rows.count()).toBeGreaterThanOrEqual(2)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY3: Monthly win rate
test('YY3 monthly win rate shows 12-month bar chart', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.getByText('月份勝率模式')).toBeVisible()
  await expect(page.locator('.yy-month-bars')).toBeVisible()
  expect(await page.locator('.yy-month-bar-col').count()).toBe(12)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY4: Lot size vs R
test('YY4 lot size effect shows big vs small lot win rates', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.getByText('倉位大小績效相關')).toBeVisible()
  const card = page.locator('.scard').filter({ hasText: '倉位大小績效相關' })
  await expect(card).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY5: Outlier contribution
test('YY5 outlier contribution shows top-10% wins share', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.getByText('離群贏單貢獻度')).toBeVisible()
  const card = page.locator('.scard').filter({ hasText: '離群贏單貢獻度' })
  await expect(card).toContainText('%')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY6: Stop distance CV
test('YY6 stop distance CV shows systematic label and CV value', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.locator('.yy-stopdist-card')).toBeVisible()
  await expect(page.locator('.yy-stopdist-card')).toContainText('CV')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY7: Planned R:R achievement distribution
test('YY7 planned RR achievement shows bar chart', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.locator('.yy-rrach-card')).toBeVisible()
  await expect(page.locator('.yy-rrach-bars')).toBeVisible()
  expect(await page.locator('.yy-rrach-col').count()).toBe(5)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY8: Expectancy phases
test('YY8 expectancy phases show early/mid/recent columns', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.getByText('期望值成長軌跡')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.yy-phase-row')).toBeVisible()
  expect(await page.locator('.yy-phase-col').count()).toBe(3)

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY9: Equity curve R²
test('YY9 equity curve R-squared shows smoothness score', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate((t) => localStorage.setItem('finlab_trade_journal', JSON.stringify(t)), makeYYTrades())
  await page.reload()

  await expect(page.locator('.card').filter({ hasText: '權益曲線平滑度' })).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.card').filter({ hasText: 'R²' }).last()).toContainText('R²')

  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
})

// YY10: Checklist compliance
test('YY10 checklist compliance shows 30-day completion rate', async ({ page }) => {
  await page.goto('/decision')
  await page.evaluate(() => {
    const today = new Date()
    for (let d = 0; d < 10; d++) {
      const dt = new Date(today)
      dt.setDate(dt.getDate() - d)
      const key = `finlab_pretrade_chk_${dt.toISOString().slice(0, 10)}`
      localStorage.setItem(key, JSON.stringify([true, true, true, true, true]))
    }
  })
  await page.reload()

  await expect(page.locator('.yy-compliance-card')).toBeVisible()
  await expect(page.locator('.yy-compliance-card')).toContainText('30天')

  await page.evaluate(() => {
    const today = new Date()
    for (let d = 0; d < 10; d++) {
      const dt = new Date(today)
      dt.setDate(dt.getDate() - d)
      localStorage.removeItem(`finlab_pretrade_chk_${dt.toISOString().slice(0, 10)}`)
    }
  })
})
