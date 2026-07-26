// @ts-check
const { test, expect } = require('@playwright/test')

// KK9：領先落後分析／主力進出頁先前只用已知有效代號（2330）做過 smoke 測試，
// 從未驗證過無效/不存在代號時的行為——後端算式在空資料上炸掉變成未預期的
// 500，只要前端把它當成「分析失敗」顯示錯誤卡片而不是整頁當機，就算通過；
// 若哪天這裡退化成放著轉圈圈或直接白畫面，這裡才會抓到。

test('領先/落後分析頁：不存在的股票代號顯示錯誤訊息，不會整頁當機', async ({ page }) => {
  await page.goto('/stocks/2330/lead-lag')
  // 側欄也有一個 placeholder 含「股票代號」的搜尋框，用 class 鎖定頁面自己的輸入框。
  await page.locator('.input-symbol').fill('ZZZZ9')
  await page.getByRole('button', { name: /分析/ }).click()

  await expect(page.locator('.error-card')).toBeVisible({ timeout: 20_000 })
})

test('主力進出頁：不存在的股票代號顯示錯誤訊息，不會整頁當機', async ({ page }) => {
  await page.goto('/stocks/2330/major-players')
  await page.locator('.input-symbol').fill('ZZZZ9')
  await page.getByRole('button', { name: /分析/ }).click()

  await expect(page.locator('.error-card')).toBeVisible({ timeout: 20_000 })
})
