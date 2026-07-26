// @ts-check
const { test, expect } = require('@playwright/test')

// KK8：鎖定 KK1 的修復。DecisionView.vue 的 fetchMajorCost/fetchChipScore
// 原本第一次抓到資料後就永久快取在 costs/healths 裡，不管是手動「立即更新」
// 按鈕還是 60 秒自動輪詢，之後都只是原地回傳同一份舊資料，主力成本／籌碼
// 分數實質上停在第一次載入當下。這裡用攔截 /major-cost 回應、驗證第二次
// 回應值真的有反映在畫面上，而不是停在第一次載入的舊值。

test('作戰台：手動「立即更新」會重新抓取主力成本（不會卡在第一次載入的舊資料）', async ({ page }) => {
  let costCallCount = 0
  await page.route('**/api/v1/stocks/2330/major-cost', async (route) => {
    costCallCount++
    const cost = costCallCount === 1 ? 111 : 222
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { cost, last_close: 100, deviation: 0, cost_verdict: '測試', cost_tone: 'flat' },
      }),
    })
  })

  await page.addInitScript(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['2330'])))
  await page.goto('/decision')

  await expect(page.locator('.mc-num').first()).toHaveText('111.00', { timeout: 20_000 })

  await page.getByRole('button', { name: '立即更新' }).click()
  await expect(page.locator('.mc-num').first()).toHaveText('222.00', { timeout: 20_000 })

  expect(costCallCount).toBeGreaterThanOrEqual(2)
})
