// @ts-check
const { test, expect } = require('@playwright/test')

// W8：自然語言選股。AI 只負責把描述解析成篩選條件，實際篩選用網站既有
// 數據跑數字比較——這裡驗前端契約：候選池大小誠實揭露、結果表可點入個股。

test('AI 選股 輸入條件後顯示解析條件與符合結果 (W8)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  await page.route('**/api/v1/screener/query', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.query).toContain('散熱')
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          query: body.query,
          criteria: { industry_keywords: ['散熱'], candidate_symbols: ['3324'], pe_max: 30, pe_min: null, revenue_yoy_min: null, description: '找散熱概念股且本益比低於30' },
          candidate_pool_size: 8, matched: [
            { symbol: '3324', name: '雙鴻', price: 850, pe: 24.8, revenue_yoy_avg: 65.6, gross_margin: 28.1, mom20_pct: 5.2 },
          ], matched_count: 1, as_of: '2026-07-21', cached: false,
        },
      }),
    })
  })

  await page.goto('/screener')
  await expect(page.getByText('AI 服務尚未設定')).toHaveCount(0)
  await page.locator('textarea').fill('找散熱概念股，本益比小於30')
  await page.getByRole('button', { name: '開始篩選' }).click()

  const result = page.locator('.result-card')
  await expect(result).toBeVisible({ timeout: 30_000 })
  await expect(result).toContainText('找散熱概念股且本益比低於30')
  await expect(result).toContainText('候選池 8 檔')
  await expect(result.locator('tbody tr')).toHaveCount(1)
  await expect(result.locator('tbody tr')).toContainText('3324')
  await expect(result.locator('tbody tr')).toContainText('雙鴻')

  await result.locator('tbody tr').click()
  await expect(page).toHaveURL(/\/stocks\/3324/)
})

test('AI 選股 沒有符合結果時顯示提示而非空白 (W8)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  await page.route('**/api/v1/screener/query', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { query: 'x', criteria: { industry_keywords: [], candidate_symbols: [], pe_max: 1, pe_min: null, revenue_yoy_min: null, description: '極端門檻' }, candidate_pool_size: 20, matched: [], matched_count: 0, as_of: '2026-07-21', cached: false },
      }),
    })
  })

  await page.goto('/screener')
  await page.locator('textarea').fill('本益比小於1')
  await page.getByRole('button', { name: '開始篩選' }).click()

  await expect(page.getByText('候選池中沒有股票符合所有篩選條件')).toBeVisible({ timeout: 30_000 })
})
