// @ts-check
const { test, expect } = require('@playwright/test')

// Position & Risk Sizing tool: loads market data (price/ATR) and computes a
// risk-based position size.
test('部位風控 loads market data and computes a position', async ({ page }) => {
  await page.goto('/risk-sizing')

  await expect(page.getByRole('heading', { name: /部位風控試算/ })).toBeVisible()

  // Market data (current price) loads from the backend.
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.mval').first()).not.toHaveText('—')

  // Sizing result renders (defaults: entry=price, stop=ATR-based).
  await expect(page.locator('.rcard.hl')).toContainText('張', { timeout: 20_000 })
  await expect(page.getByText('每股風險')).toBeVisible()

  // A large account should size at least one lot.
  await page.getByRole('spinbutton').first().fill('50000000')
  await expect(page.locator('.rcard.hl strong')).not.toContainText('0 張')

  // Risk-discipline checklist is shown.
  await expect(page.locator('.checklist li').first()).toBeVisible()
})

test('凱利 computes half-Kelly and applies it to risk %', async ({ page }) => {
  await page.goto('/risk-sizing')
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })

  const kellyInputs = page.locator('.kelly-block .kelly-grid input')
  await kellyInputs.nth(0).fill('50')  // win rate %
  await kellyInputs.nth(1).fill('1.5') // profit factor

  // Kelly = 0.5*(1.5-1)/1.5 = 0.1667 -> half-Kelly = 8.33% (under the 10% cap)
  await expect(page.locator('.kelly-block .rcard.hl strong')).toHaveText('8.3%')

  await page.getByRole('button', { name: '套用到單筆風險%' }).click()
  await expect(page.getByText('風險預算 (資金×8.3%)')).toBeVisible()
})

test('凱利 從回測帶入 fills win rate and profit factor', async ({ page }) => {
  await page.route('**/api/v1/backtest/run', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { performance: { win_rate: 0.55, profit_factor: 1.8, total_trades: 42 } } }),
    })
  })
  await page.goto('/risk-sizing')
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })

  await page.getByRole('button', { name: /從回測帶入/ }).click()

  const kellyInputs = page.locator('.kelly-block .kelly-grid input')
  await expect(kellyInputs.nth(0)).toHaveValue('55')
  await expect(kellyInputs.nth(1)).toHaveValue('1.8')
  await expect(page.locator('.kelly-block .rcard.hl strong')).toContainText('%')
})

test('凱利 從交易日誌帶入 uses real journal stats', async ({ page }) => {
  await page.goto('/risk-sizing')
  // 2 wins (+20k, +10k), 1 loss (-15k) -> win rate 67%, PF = 30k/15k = 2.
  await page.evaluate(() => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 120, lots: 1 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 85, lots: 1 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 110, lots: 1 },
    ]))
  })
  await expect(page.locator('.mval').first()).toBeVisible({ timeout: 60_000 })

  await page.getByRole('button', { name: '從交易日誌帶入' }).click()

  const kellyInputs = page.locator('.kelly-block .kelly-grid input')
  await expect(kellyInputs.nth(0)).toHaveValue('67')
  await expect(kellyInputs.nth(1)).toHaveValue('2')
})

test('部位風控 shows a setup-score panel', async ({ page }) => {
  await page.goto('/risk-sizing')
  await expect(page.locator('.setup-panel')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.setup-score')).toContainText('/100')
  await expect(page.getByText(/進場評分：/)).toBeVisible()
  await expect(page.locator('.setup-components .comp')).toHaveCount(4)
})
