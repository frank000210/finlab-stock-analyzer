// @ts-check
const { test, expect } = require('@playwright/test')

// P9：部分互動元素（總覽頁摘要卡、決策面板搜尋下拉）之前是純 div/li 綁
// @click，鍵盤使用者選不到。改成 role=link/option + tabindex + Enter/Space
// 觸發，不影響原本的滑鼠點擊行為。

test('總覽頁摘要卡可用鍵盤 Enter 導頁 (P9)', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.locator('.summary-card').first()).toBeVisible({ timeout: 20_000 })

  const seasonalCard = page.locator('.summary-card[aria-label="季節性分析"]')
  await seasonalCard.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/seasonal/)
})

test('決策面板搜尋下拉選項可用鍵盤 Tab+Enter 選取 (P9)', async ({ page }) => {
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: '2454', name_zh: '聯發科' }] } }),
    })
  })
  await page.goto('/decision')

  const input = page.locator('.watchlist-input')
  await input.fill('聯發')
  const option = page.locator('.watchlist-dropdown li', { hasText: '2454' })
  await expect(option).toBeVisible({ timeout: 10_000 })

  await option.focus()
  await page.keyboard.press('Enter')

  await expect(input).toHaveValue('')
  const watchlist = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist') || '[]'))
  expect(watchlist).toContain('2454')
})
