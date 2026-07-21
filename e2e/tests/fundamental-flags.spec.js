// @ts-check
const { test, expect } = require('@playwright/test')

// W3：財報矛盾偵測——純規則，不打 LLM，頁面載入即自動顯示。用國巨 2327
// 的真實案例形狀構造資料：營收/毛利率上升但 EPS 年減逾三成。

test('分析頁 財報矛盾偵測自動顯示，免點擊免等待 (W3)', async ({ page }) => {
  await page.route('**/api/v1/analysis/2327/fundamental*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          revenue_monthly: [
            { month: '2026-04', revenue: 14000000000, yoy: 22.0 },
            { month: '2026-05', revenue: 15000000000, yoy: 47.5 },
            { month: '2026-06', revenue: 15300000000, yoy: 38.9 },
          ],
          eps_quarterly: [
            { quarter: '2024Q4', eps: 7.07 }, { quarter: '2025Q1', eps: 10.77 },
            { quarter: '2025Q2', eps: 9.74 }, { quarter: '2025Q3', eps: 3.1 },
            { quarter: '2025Q4', eps: 3.29 }, { quarter: '2026Q1', eps: 3.9 },
          ],
          margins: [
            { quarter: '2025Q2', gross_margin: 35.56, operating_margin: 21.49 },
            { quarter: '2025Q3', gross_margin: 36.19, operating_margin: 22.86 },
            { quarter: '2025Q4', gross_margin: 37.3, operating_margin: 24.28 },
            { quarter: '2026Q1', gross_margin: 38.1, operating_margin: 25.19 },
          ],
          debt_ratios: [],
        },
      }),
    })
  })

  await page.goto('/stocks/2327')
  const flags = page.locator('.fund-flags')
  await expect(flags).toBeVisible({ timeout: 30_000 })
  await expect(flags).toContainText('營收與獲利明顯脫鉤')
  await expect(flags).toContainText('毛利率')
})

test('分析頁 財報數據正常時不顯示矛盾標記 (W3)', async ({ page }) => {
  await page.route('**/api/v1/analysis/2330/fundamental*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          revenue_monthly: [{ month: '2026-06', revenue: 200000000000, yoy: 8.0 }],
          eps_quarterly: [
            { quarter: '2025Q1', eps: 10 }, { quarter: '2025Q2', eps: 10.2 },
            { quarter: '2025Q3', eps: 10.5 }, { quarter: '2025Q4', eps: 10.8 },
            { quarter: '2026Q1', eps: 11 },
          ],
          margins: [
            { quarter: '2025Q2', gross_margin: 50 }, { quarter: '2025Q3', gross_margin: 50.2 },
            { quarter: '2025Q4', gross_margin: 50.1 }, { quarter: '2026Q1', gross_margin: 50.3 },
          ],
          debt_ratios: [],
        },
      }),
    })
  })

  await page.goto('/stocks/2330')
  await expect(page.getByText('基本面重點')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.fund-flags')).toHaveCount(0)
})
