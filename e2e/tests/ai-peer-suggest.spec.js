// @ts-check
const { test, expect } = require('@playwright/test')

// W1：AI 一鍵建議同業，取代手動複製提示詞去 Gemini 再貼回的流程。

test('分析頁 一鍵 AI 建議同業，候選經驗證後可勾選加入 (W1)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2327/peers', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { symbol: '2327', industry: '電子工業', group_source: 'industry', peers: [] } }),
      })
    } else {
      await route.continue()
    }
  })
  await page.route('**/api/v1/stocks/2327/peer-comparison', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2327', industry: '電子工業', group_source: 'industry', target: { symbol: '2327', name: '國巨' }, peers: [] } }),
    })
  })
  await page.route('**/api/v1/stocks/2327/peers/ai-suggest', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2327',
          candidates: [
            { symbol: '2492', name: '華新科', reason: '同為MLCC大廠', valid: true },
            { symbol: '9999', name: '', reason: '', valid: false },
          ],
          raw_count: 2,
        },
      }),
    })
  })

  await page.goto('/stocks/2327')
  await expect(page.getByText('目前沒有可比較的同業')).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: '編輯同業' }).click()
  const suggestBtn = page.getByRole('button', { name: /一鍵 AI 建議/ })
  await expect(suggestBtn).toBeVisible()
  await suggestBtn.click()

  const candidates = page.locator('.ai-candidates')
  await expect(candidates).toBeVisible({ timeout: 30_000 })
  await expect(candidates).toContainText('2492 華新科')
  await expect(candidates).toContainText('同為MLCC大廠')
  await expect(candidates).toContainText('查無此代碼')

  // 無效代碼的 checkbox 應被 disable，不能誤加入
  const invalidCheckbox = candidates.locator('.ai-cand', { hasText: '9999' }).locator('input[type="checkbox"]')
  await expect(invalidCheckbox).toBeDisabled()
})
