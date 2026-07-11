// @ts-check
const { test, expect } = require('@playwright/test')

// F7: 風險模擬 previously required guessing win rate / payoff by hand, while
// 部位風控 already had a "從交易日誌帶入" button for the same purpose. Adds
// the same real-stats import here, computed directly in R-multiples (the
// same unit the simulation itself uses) rather than dollar profit factor.
test('風險模擬 從交易日誌帶入 fills real win-rate/payoff (F7)', async ({ page }) => {
  await page.goto('/monte-carlo')
  await page.evaluate(() => {
    // 2 wins (+2.0R, +1.5R) + 2 losses (-1.0R, -1.5R) -> winRate=50%, payoff=1.75/1.25=1.4
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 120 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 115 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 90 },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 85 },
    ]))
  })
  await page.reload()

  await page.getByRole('button', { name: '從交易日誌帶入' }).click()

  const inputs = page.locator('.field input[type="number"]')
  await expect(inputs.nth(0)).toHaveValue('50')
  await expect(inputs.nth(1)).toHaveValue('1.4')
  await expect(page.getByText(/已帶入你 4 筆實戰統計/)).toBeVisible()
})

test('風險模擬 交易日誌無紀錄時顯示提示而不噴錯 (F7)', async ({ page }) => {
  await page.goto('/monte-carlo')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  await page.getByRole('button', { name: '從交易日誌帶入' }).click()
  await expect(page.getByText('交易日誌尚無已平倉紀錄')).toBeVisible()
})
