// @ts-check
const { test, expect } = require('@playwright/test')

// W5：新聞可信度檢查頁——原本只有後端 API 沒有前端頁面，這裡新建。
// 五層規則式評分＋選填 AI 語意層（不計入分數）。

test('新聞可信度頁 檢查後顯示五層分數與 AI 語意層 (W5)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  await page.route('**/api/v1/news/crawled-data*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.route('**/api/v1/news/check-credibility', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          url: 'https://cnyes.com/test', title: '台積電法說會上修展望', source: 'cnyes.com',
          overall_score: 78.5, verdict: 'CREDIBLE',
          layers: [
            { layer: 'media_source', score: 82, weight: 0.3, detail: '' },
            { layer: 'cofacts', score: 50, weight: 0.25, detail: '' },
            { layer: 'content', score: 90, weight: 0.2, detail: '' },
            { layer: 'cross_validation', score: 80, weight: 0.15, detail: '' },
            { layer: 'timeliness', score: 95, weight: 0.1, detail: '' },
          ],
          summary: '整體判定為可信', llm_assessment: { available: true, note: '用詞中性，數據可查證。' },
          published_at: null, checked_at: '2026-07-20T10:00:00',
        },
      }),
    })
  })

  await page.goto('/news-checker')
  await page.getByPlaceholder('https://...').fill('https://cnyes.com/test')
  await page.getByPlaceholder('新聞標題').fill('台積電法說會上修展望')
  await page.getByRole('button', { name: '檢查可信度' }).click()

  const result = page.locator('.result-card')
  await expect(result).toBeVisible({ timeout: 30_000 })
  await expect(result).toContainText('78.5')
  await expect(result).toContainText('可信')
  await expect(result.locator('.layer-row')).toHaveCount(5)
  await expect(result.locator('.llm-layer')).toContainText('用詞中性，數據可查證')
})

test('新聞可信度頁 AI 語意層失敗時不影響五層分數顯示 (W5)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  await page.route('**/api/v1/news/crawled-data*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.route('**/api/v1/news/check-credibility', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          url: 'https://x.com/test', title: '測試', source: 'x.com', overall_score: 55, verdict: 'UNCERTAIN',
          layers: [
            { layer: 'media_source', score: 55, weight: 0.3, detail: '' },
            { layer: 'cofacts', score: 50, weight: 0.25, detail: '' },
            { layer: 'content', score: 55, weight: 0.2, detail: '' },
            { layer: 'cross_validation', score: 55, weight: 0.15, detail: '' },
            { layer: 'timeliness', score: 60, weight: 0.1, detail: '' },
          ],
          summary: '不確定', llm_assessment: null, published_at: null, checked_at: '2026-07-20T10:00:00',
        },
      }),
    })
  })

  await page.goto('/news-checker')
  await page.getByPlaceholder('https://...').fill('https://x.com/test')
  await page.getByRole('button', { name: '檢查可信度' }).click()

  const result = page.locator('.result-card')
  await expect(result).toBeVisible({ timeout: 30_000 })
  await expect(result.locator('.layer-row')).toHaveCount(5)
  await expect(result.locator('.llm-layer')).toHaveCount(0)
  await expect(result).toContainText('未取得 AI 語意層結果')
})
