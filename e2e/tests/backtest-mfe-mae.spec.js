// @ts-check
const { test, expect } = require('@playwright/test')

// B7: MFE/MAE — how much profit was on the table / how much heat was taken
// during each trade's holding period, not just the final exit result.
test('回測顯示 MFE/MAE 分析卡片與交易明細欄位', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/stocks/2330/backtest')
  await page.getByRole('button', { name: /執行回測/ }).click()

  const card = page.locator('.mfe-card')
  await expect(card).toBeVisible({ timeout: 120_000 })
  await expect(card).toContainText('平均 MFE')
  await expect(card).toContainText('平均 MAE')
  await expect(card).toContainText('最深 MAE')

  // 交易明細表要有 MFE%/MAE% 欄位且有實際數字（不是全部 —）
  const headers = page.locator('.data-table thead th')
  await expect(headers).toContainText(['進場日', '出場日', '進場價', '出場價', '報酬%', '持有天數', 'MFE%', 'MAE%'])
  const firstMfeCell = page.locator('.data-table tbody tr').first().locator('td').nth(6)
  await expect(firstMfeCell).not.toHaveText('—')
})
