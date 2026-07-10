// @ts-check
const { test, expect } = require('@playwright/test')

// D11: Ctrl/Cmd+K global quick switcher — pages + stock search with names.
test('Ctrl+K 開啟快速切換並跳頁', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Control+k')

  const panel = page.locator('.qs-panel')
  await expect(panel).toBeVisible()

  // 輸入頁面關鍵字 → 選中 → Enter 前往
  await page.locator('.qs-input').fill('作戰')
  await expect(panel).toContainText('作戰台')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/command/)
  await expect(panel).toBeHidden()
})

test('Ctrl+K 搜個股顯示名稱並跳分析頁', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: '2330', name_zh: '台積電', market: 'twse', industry: '半導體業' }] } }),
    })
  })
  await page.goto('/journal')
  await page.keyboard.press('Control+k')
  await page.locator('.qs-input').fill('2330')

  const stockItem = page.locator('.qs-item', { hasText: '台積電' })
  await expect(stockItem).toBeVisible()
  await stockItem.click()
  await expect(page).toHaveURL(/\/stocks\/2330/)
})

test('Esc 關閉快速切換', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Control+k')
  await expect(page.locator('.qs-panel')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.qs-panel')).toBeHidden()
})
